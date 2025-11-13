"""WhatsApp-specific pipeline helpers."""

from __future__ import annotations

import logging
import re
import zipfile
from datetime import date as date_type
from pathlib import Path
from zoneinfo import ZoneInfo

from google import genai

from egregora.output_adapters.mkdocs import resolve_site_paths

logger = logging.getLogger(__name__)


def discover_chat_file(zip_path: Path) -> tuple[str, str]:
    """Find the chat .txt file in the ZIP archive and infer the group name."""
    with zipfile.ZipFile(zip_path) as zf:
        candidates: list[tuple[int, str, str]] = []
        for member in zf.namelist():
            if not member.endswith(".txt") or member.startswith("__"):
                continue

            pattern = r"WhatsApp(?: Chat with|.*) (.+)\\.txt"
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

        candidates.sort(reverse=True, key=lambda item: item[0])
        _, group_name, member = candidates[0]
        return (group_name, member)


def process_whatsapp_export(
    zip_path: Path,
    output_dir: Path = Path("output"),
    *,
    step_size: int = 100,
    step_unit: str = "messages",
    overlap_ratio: float = 0.2,
    enable_enrichment: bool = True,
    from_date: date_type | None = None,
    to_date: date_type | None = None,
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
    """Delegate to the orchestration pipeline for WhatsApp ZIP exports."""
    from egregora.orchestration.write_pipeline import process_whatsapp_export as _process

    return _process(
        zip_path,
        output_dir,
        step_size=step_size,
        step_unit=step_unit,
        overlap_ratio=overlap_ratio,
        enable_enrichment=enable_enrichment,
        from_date=from_date,
        to_date=to_date,
        timezone=timezone,
        gemini_api_key=gemini_api_key,
        model=model,
        batch_threshold=batch_threshold,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
        max_prompt_tokens=max_prompt_tokens,
        use_full_context_window=use_full_context_window,
        client=client,
    )
