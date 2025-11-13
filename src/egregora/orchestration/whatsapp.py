"""WhatsApp-specific orchestration helpers."""

from __future__ import annotations

import logging
import re
import zipfile
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from google import genai

from egregora.output_adapters.mkdocs_site import resolve_site_paths

logger = logging.getLogger(__name__)


def discover_chat_file(zip_path: Path) -> tuple[str, str]:
    """Find the chat .txt file in the ZIP and extract group name."""
    with zipfile.ZipFile(zip_path) as zf:
        candidates: list[tuple[int, str, str]] = []
        for member in zf.namelist():
            if member.endswith(".txt") and not member.startswith("__"):
                pattern = r"WhatsApp(?: Chat with|.*) (.+)\.txt"
                match = re.match(pattern, Path(member).name)
                file_info = zf.getinfo(member)
                score = file_info.file_size
                if match:
                    score += 1_000_000
                    group_name = match.group(1)
                else:
                    group_name = Path(member).stem
                candidates.append((score, group_name, member))
        if not candidates:
            msg = f"No WhatsApp chat file found in {zip_path}"
            raise ValueError(msg)
        candidates.sort(reverse=True, key=lambda x: x[0])
        _, group_name, member = candidates[0]
        return group_name, member


def process_whatsapp_export(
    zip_path: Path,
    output_dir: Path = Path("output"),
    *,
    step_size: int = 100,
    step_unit: str = "messages",
    overlap_ratio: float = 0.2,
    enable_enrichment: bool = True,
    from_date: date | None = None,
    to_date: date | None = None,
    timezone: str | ZoneInfo | None = None,
    gemini_api_key: str | None = None,
    model: str | None = None,
    batch_threshold: int = 10,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    max_prompt_tokens: int = 100_000,
    use_full_context_window: bool = False,
    client: genai.Client | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Public entry point for WhatsApp exports."""
    from egregora.config.settings import load_egregora_config
    from egregora.orchestration import write_pipeline

    output_dir = output_dir.expanduser().resolve()
    site_paths = resolve_site_paths(output_dir)

    base_config = load_egregora_config(site_paths.site_root)

    egregora_config = base_config.model_copy(
        deep=True,
        update={
            "pipeline": base_config.pipeline.model_copy(
                update={
                    "step_size": step_size,
                    "step_unit": step_unit,
                    "overlap_ratio": overlap_ratio,
                    "timezone": str(timezone) if timezone else None,
                    "from_date": from_date.isoformat() if from_date else None,
                    "to_date": to_date.isoformat() if to_date else None,
                    "batch_threshold": batch_threshold,
                    "max_prompt_tokens": max_prompt_tokens,
                    "use_full_context_window": use_full_context_window,
                },
            ),
            "enrichment": base_config.enrichment.model_copy(update={"enabled": enable_enrichment}),
            "rag": base_config.rag.model_copy(
                update={
                    "mode": retrieval_mode,
                    "nprobe": retrieval_nprobe if retrieval_nprobe is not None else base_config.rag.nprobe,
                    "overfetch": (
                        retrieval_overfetch if retrieval_overfetch is not None else base_config.rag.overfetch
                    ),
                },
            ),
        },
    )

    logger.debug("Starting WhatsApp pipeline for zip=%s output=%s", zip_path, output_dir)
    return write_pipeline.run(
        source="whatsapp",
        input_path=zip_path,
        output_dir=output_dir,
        config=egregora_config,
        api_key=gemini_api_key,
        model_override=model,
        client=client,
    )
