"""WhatsApp-specific pipeline functions."""

import logging
import re
import zipfile
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from google import genai

from egregora.config import resolve_site_paths

logger = logging.getLogger(__name__)


def discover_chat_file(zip_path: Path) -> tuple[str, str]:
    """Find the chat .txt file in the ZIP and extract group name."""
    with zipfile.ZipFile(zip_path) as zf:
        candidates = []
        for member in zf.namelist():
            if member.endswith(".txt") and (not member.startswith("__")):
                pattern = "WhatsApp(?: Chat with|.*) (.+)\\.txt"
                match = re.match(pattern, Path(member).name)
                file_info = zf.getinfo(member)
                score = file_info.file_size
                if match:
                    score += 1000000
                    group_name = match.group(1)
                else:
                    group_name = Path(member).stem
                candidates.append((score, group_name, member))
        if not candidates:
            msg = f"No WhatsApp chat file found in {zip_path}"
            raise ValueError(msg)
        candidates.sort(reverse=True, key=lambda x: x[0])
        _, group_name, member = candidates[0]
        return (group_name, member)


def process_whatsapp_export(
    zip_path: Path,
    output_dir: Path = Path("output"),
    period: str = "day",
    *,
    enable_enrichment: bool = True,
    from_date: date | None = None,
    to_date: date | None = None,
    timezone: str | ZoneInfo | None = None,
    gemini_api_key: str | None = None,
    model: str | None = None,
    resume: bool = True,
    batch_threshold: int = 10,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    client: genai.Client | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Public entry point for WhatsApp exports (backward compatibility wrapper).

    MODERN (Phase 2): This is now a thin wrapper around run_source_pipeline.
    The CLI uses run_source_pipeline directly. This function exists for:
    - Backward compatibility with existing code/tests
    - Convenient WhatsApp-specific interface

    For new code, prefer using run_source_pipeline(source="whatsapp", ...) directly.

    Args:
        zip_path: WhatsApp export ZIP file
        output_dir: Where to save posts and profiles
        period: "day", "week", or "month"
        enable_enrichment: Add URL/media context
        from_date: Only process messages from this date onwards (date object)
        to_date: Only process messages up to this date (date object)
        timezone: ZoneInfo timezone object (WhatsApp export phone timezone)
        gemini_api_key: Google Gemini API key
        model: Gemini model to use (overrides mkdocs.yml config)
        resume: Whether to resume from a previous run
        batch_threshold: The threshold for switching to batch processing
        retrieval_mode: The retrieval mode to use
        retrieval_nprobe: The number of probes to use for retrieval
        retrieval_overfetch: The overfetch factor to use for retrieval
        client: Optional Gemini client (will be created if not provided)

    Returns:
        Dict mapping period to {'posts': [...], 'profiles': [...]}

    """
    from egregora.config.loader import load_egregora_config
    from egregora.pipeline.runner import run_source_pipeline

    # MODERN (Phase 2): Delegate to run_source_pipeline with config
    output_dir = output_dir.expanduser().resolve()
    site_paths = resolve_site_paths(output_dir)

    # Load config and override with CLI parameters
    base_config = load_egregora_config(site_paths.site_root)

    egregora_config = base_config.model_copy(
        deep=True,
        update={
            "pipeline": base_config.pipeline.model_copy(
                update={
                    "period": period,
                    "timezone": str(timezone) if timezone else None,
                    "from_date": from_date.isoformat() if from_date else None,
                    "to_date": to_date.isoformat() if to_date else None,
                    "resume": resume,
                    "batch_threshold": batch_threshold,
                }
            ),
            "enrichment": base_config.enrichment.model_copy(update={"enabled": enable_enrichment}),
            "rag": base_config.rag.model_copy(
                update={
                    "mode": retrieval_mode,
                    "nprobe": retrieval_nprobe if retrieval_nprobe is not None else base_config.rag.nprobe,
                    "overfetch": retrieval_overfetch
                    if retrieval_overfetch is not None
                    else base_config.rag.overfetch,
                }
            ),
        },
    )

    return run_source_pipeline(
        source="whatsapp",
        input_path=zip_path,
        output_dir=output_dir,
        config=egregora_config,
        api_key=gemini_api_key,
        model_override=model,
        client=client,
    )
