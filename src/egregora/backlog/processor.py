"""High level orchestration for backlog processing."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from ..config import PipelineConfig, load_backlog_config
from ..pipeline import Pipeline
from .checkpoint import CheckpointManager
from .estimator import CostEstimate, estimate_costs
from .logger import configure_logger
from .scanner import PendingDay, scan_pending_days


@dataclass(slots=True)
class ProcessingResult:
    """Result of an attempt to process a single day."""

    date: date
    zip_path: Path
    output_path: Optional[Path]
    status: str
    duration_seconds: float
    error: Optional[str] = None


class BacklogProcessor:
    """Process WhatsApp backlog archives sequentially."""

    def __init__(
        self,
        config_path: str | Path | None = None,
        checkpoint_file: str | Path | None = None,
        *,
        pipeline_config: PipelineConfig | None = None,
    ) -> None:
        self.backlog_config = load_backlog_config(config_path)
        checkpoint_path = (
            Path(checkpoint_file)
            if checkpoint_file
            else Path(self.backlog_config.checkpoint.file)
        )
        self.checkpoint_manager = CheckpointManager(
            checkpoint_path, backup=self.backlog_config.checkpoint.backup
        )
        self.checkpoint_state = self.checkpoint_manager.load()
        self.pipeline_config = pipeline_config or PipelineConfig.with_defaults()
        self.logger = configure_logger(
            self.backlog_config,
            stream=self.backlog_config.logging.detailed_per_day,
        )
        self.pipeline = Pipeline(
            self.pipeline_config,
            batch_mode=True,
            logger=self.logger,
        )

    # ------------------------------------------------------------------
    # Discovery & estimation helpers
    # ------------------------------------------------------------------
    def scan_pending_days(self, zip_dir: str | Path, output_dir: str | Path) -> List[PendingDay]:
        zip_path = Path(zip_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        return scan_pending_days(zip_path, output_path)

    def estimate_costs(self, pending_days: Iterable[PendingDay]) -> CostEstimate:
        return estimate_costs(pending_days, self.backlog_config)

    # ------------------------------------------------------------------
    # Core processing methods
    # ------------------------------------------------------------------
    def process_day(
        self,
        zip_file: str | Path,
        day: date,
        *,
        skip_enrichment: bool = False,
        force_rebuild: bool = False,
    ) -> ProcessingResult:
        start = time.monotonic()
        zip_path = Path(zip_file)
        if not zip_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {zip_path}")

        output_path = self.pipeline_config.newsletters_dir / f"{day.isoformat()}.md"
        if output_path.exists() and not force_rebuild:
            return ProcessingResult(
                date=day,
                zip_path=zip_path,
                output_path=output_path,
                status="skipped",
                duration_seconds=0.0,
            )

        try:
            result = self.pipeline.process_day(zip_path, day, skip_enrichment=skip_enrichment)
            duration = time.monotonic() - start
            return ProcessingResult(
                date=day,
                zip_path=zip_path,
                output_path=result.output_path,
                status="success",
                duration_seconds=round(duration, 2),
            )
        except Exception as exc:  # pragma: no cover - defensive
            duration = time.monotonic() - start
            return ProcessingResult(
                date=day,
                zip_path=zip_path,
                output_path=None,
                status="failed",
                duration_seconds=round(duration, 2),
                error=str(exc),
            )

    def process_batch(
        self,
        pending_days: Iterable[PendingDay],
        *,
        max_per_run: Optional[int] = None,
        skip_enrichment: bool = False,
        force_rebuild: bool = False,
        dry_run: bool = False,
    ) -> List[ProcessingResult]:
        queue = list(pending_days)
        self.checkpoint_state.total_pending = len(queue)
        processed: List[ProcessingResult] = []
        failures: List[str] = []

        if not queue:
            self.logger.info("Nenhum dia pendente encontrado para processamento.")

        for index, pending in enumerate(queue, start=1):
            if max_per_run is not None and len(processed) >= max_per_run:
                break

            if pending.already_processed and not force_rebuild:
                self.logger.info(
                    "[Backlog] %s já processado. Pulando.", pending.date.isoformat()
                )
                processed.append(
                    ProcessingResult(
                        date=pending.date,
                        zip_path=pending.zip_path,
                        output_path=pending.newsletter_path,
                        status="skipped",
                        duration_seconds=0.0,
                    )
                )
                continue

            if dry_run:
                processed.append(
                    ProcessingResult(
                        date=pending.date,
                        zip_path=pending.zip_path,
                        output_path=None,
                        status="dry-run",
                        duration_seconds=0.0,
                    )
                )
                continue

            self.logger.info(
                "[Backlog] Processando %s (%d/%d)",
                pending.date.isoformat(),
                index,
                len(queue),
            )
            retries = 0
            max_retries = max(1, self.backlog_config.processing.max_retries)
            last_result: ProcessingResult | None = None
            while retries < max_retries:
                result = self.process_day(
                    pending.zip_path,
                    pending.date,
                    skip_enrichment=skip_enrichment,
                    force_rebuild=force_rebuild,
                )
                last_result = result
                if result.status != "failed":
                    break
                retries += 1
                time.sleep(2**retries)

            if last_result is None:
                continue

            processed.append(last_result)
            if last_result.status == "failed" and last_result.error:
                self.logger.error(
                    "[Backlog] Falha ao processar %s: %s",
                    pending.date.isoformat(),
                    last_result.error,
                )
                failures.append(f"{pending.date.isoformat()}: {last_result.error}")
            else:
                self.save_checkpoint(last_result.date.isoformat())

            if last_result.status == "success":
                self.logger.info(
                    "[Backlog] Dia %s concluído em %.2fs.",
                    pending.date.isoformat(),
                    last_result.duration_seconds,
                )
                delay = max(self.backlog_config.processing.delay_between_days, 0)
                if delay:
                    time.sleep(delay)

        if failures:
            self.logger.warning("Falhas durante o processamento: %s", "; ".join(failures))

        success_count = sum(1 for result in processed if result.status == "success")
        self.checkpoint_state.total_processed += success_count
        self.checkpoint_state.total_pending = max(
            self.checkpoint_state.total_pending - len(processed), 0
        )
        if failures:
            self.checkpoint_state.failed_dates.extend(failures)
        self.checkpoint_state.statistics.update(
            {
                "last_run_processed": success_count,
                "last_run_total": len(processed),
                "last_run_failures": len(failures),
                "skip_enrichment": skip_enrichment,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.checkpoint_manager.save(self.checkpoint_state)

        return processed

    # ------------------------------------------------------------------
    # Checkpoint helpers
    # ------------------------------------------------------------------
    def save_checkpoint(self, last_processed_date: Optional[str]) -> None:
        self.checkpoint_state.last_processed_date = last_processed_date
        self.checkpoint_manager.save(self.checkpoint_state)

    def load_checkpoint(self) -> Optional[str]:
        state = self.checkpoint_manager.load()
        self.checkpoint_state = state
        return state.last_processed_date

    def resume_processing(
        self,
        pending_days: Iterable[PendingDay],
        *,
        skip_enrichment: bool = False,
        force_rebuild: bool = False,
    ) -> List[ProcessingResult]:
        last_date = self.load_checkpoint()
        if last_date is None:
            return self.process_batch(
                pending_days,
                skip_enrichment=skip_enrichment,
                force_rebuild=force_rebuild,
            )

        resume_after = datetime.strptime(last_date, "%Y-%m-%d").date()
        filtered = [day for day in pending_days if day.date > resume_after]
        return self.process_batch(
            filtered,
            skip_enrichment=skip_enrichment,
            force_rebuild=force_rebuild,
        )


__all__ = ["BacklogProcessor", "ProcessingResult"]
