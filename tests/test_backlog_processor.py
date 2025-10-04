"""Tests for the high-level backlog processor."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import List

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from egregora.backlog.processor import BacklogProcessor
from egregora.pipeline import PipelineResult
from test_framework.helpers import create_test_zip


class DummyPipeline:
    def __init__(self, output_dir: Path, *, fail_times: int = 0):
        self.output_dir = output_dir
        self.fail_times = fail_times
        self.calls: List[tuple[Path, date, bool]] = []

    def process_day(self, zip_path: Path, day: date, *, skip_enrichment: bool = False) -> PipelineResult:
        self.calls.append((zip_path, day, skip_enrichment))
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("erro simulado")

        output_path = self.output_dir / f"{day.isoformat()}.md"
        output_path.write_text("newsletter gerada", encoding="utf-8")
        return PipelineResult(
            output_path=output_path,
            processed_dates=[day],
            previous_newsletter_path=output_path,
            previous_newsletter_found=False,
            enrichment=None,
        )


def _write_config(base_dir: Path) -> Path:
    config_path = base_dir / "config.yaml"
    config_path.write_text(
        f"""
logging:
  file: {base_dir / 'log.txt'}
  level: INFO
  detailed_per_day: false
checkpoint:
  file: {base_dir / 'checkpoint.json'}
  backup: false
"""
    )
    return config_path


def _setup_processor(base_dir: Path) -> BacklogProcessor:
    zip_dir = base_dir / "zips"
    output_dir = base_dir / "out"
    zip_dir.mkdir()
    output_dir.mkdir()

    config_path = _write_config(base_dir)

    from egregora.config import PipelineConfig

    pipeline_config = PipelineConfig.with_defaults(
        zips_dir=zip_dir,
        newsletters_dir=output_dir,
        media_dir=output_dir / "media",
    )
    pipeline_config.rag.enabled = False

    processor = BacklogProcessor(
        config_path=config_path,
        checkpoint_file=base_dir / "checkpoint.json",
        pipeline_config=pipeline_config,
    )
    processor.backlog_config.processing.delay_between_days = 0
    return processor


def _scan(processor: BacklogProcessor, zip_dir: Path, output_dir: Path):
    return processor.scan_pending_days(zip_dir, output_dir)


def test_process_single_day_success(tmp_path: Path) -> None:
    processor = _setup_processor(tmp_path)
    zip_dir = processor.pipeline_config.zips_dir
    output_dir = processor.pipeline_config.newsletters_dir

    create_test_zip("01/10/2024 09:00 - Alice: Olá", zip_dir / "2024-10-01.zip")
    pending = _scan(processor, zip_dir, output_dir)

    dummy = DummyPipeline(output_dir)
    processor.pipeline = dummy

    results = processor.process_batch(pending, skip_enrichment=True)
    assert results[0].status == "success"
    assert (output_dir / "2024-10-01.md").exists()
    assert dummy.calls[0][2] is True


def test_process_handles_missing_zip(tmp_path: Path) -> None:
    processor = _setup_processor(tmp_path)
    with pytest.raises(FileNotFoundError):
        processor.process_day(tmp_path / "missing.zip", date(2024, 10, 1))


def test_process_skips_existing_when_configured(tmp_path: Path) -> None:
    processor = _setup_processor(tmp_path)
    zip_dir = processor.pipeline_config.zips_dir
    output_dir = processor.pipeline_config.newsletters_dir

    create_test_zip("01/10/2024 09:00 - Alice: Olá", zip_dir / "2024-10-01.zip")
    (output_dir / "2024-10-01.md").write_text("já existe", encoding="utf-8")

    result = processor.process_day(zip_dir / "2024-10-01.zip", date(2024, 10, 1))
    assert result.status == "skipped"


def test_process_forces_rebuild_when_configured(tmp_path: Path) -> None:
    processor = _setup_processor(tmp_path)
    zip_dir = processor.pipeline_config.zips_dir
    output_dir = processor.pipeline_config.newsletters_dir

    create_test_zip("01/10/2024 09:00 - Alice: Olá", zip_dir / "2024-10-01.zip")
    (output_dir / "2024-10-01.md").write_text("velho", encoding="utf-8")

    dummy = DummyPipeline(output_dir)
    processor.pipeline = dummy

    result = processor.process_day(
        zip_dir / "2024-10-01.zip",
        date(2024, 10, 1),
        force_rebuild=True,
    )
    assert result.status == "success"
    assert dummy.calls


def test_process_retries_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    processor = _setup_processor(tmp_path)
    zip_dir = processor.pipeline_config.zips_dir
    output_dir = processor.pipeline_config.newsletters_dir

    create_test_zip("01/10/2024 09:00 - Alice: Olá", zip_dir / "2024-10-01.zip")
    pending = _scan(processor, zip_dir, output_dir)

    dummy = DummyPipeline(output_dir, fail_times=1)
    processor.pipeline = dummy

    monkeypatch.setattr("egregora.backlog.processor.time.sleep", lambda *_: None)

    results = processor.process_batch(pending, skip_enrichment=False)
    assert results[0].status == "success"
    assert len(dummy.calls) == 2


def test_process_respects_max_per_run(tmp_path: Path) -> None:
    processor = _setup_processor(tmp_path)
    zip_dir = processor.pipeline_config.zips_dir
    output_dir = processor.pipeline_config.newsletters_dir

    for idx in range(1, 4):
        create_test_zip(
            f"0{idx}/10/2024 09:00 - Alice: Olá",
            zip_dir / f"2024-10-0{idx}.zip",
        )

    pending = _scan(processor, zip_dir, output_dir)
    dummy = DummyPipeline(output_dir)
    processor.pipeline = dummy

    results = processor.process_batch(pending, max_per_run=2, skip_enrichment=True)
    assert len(results) == 2
    assert len(dummy.calls) == 2
