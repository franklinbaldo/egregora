"""Egregora v2: Ultra-simple WhatsApp to blog pipeline."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any, Callable, cast

__version__ = "2.0.0"

__all__ = ["process_whatsapp_export"]


_ProcessWhatsAppExport = Callable[..., dict[str, dict[str, list[str]]]]


def process_whatsapp_export(  # noqa: PLR0913
    zip_path: Path,
    output_dir: Path = Path("output"),
    period: str = "day",
    enable_enrichment: bool = True,
    from_date: Any = None,
    to_date: Any = None,
    timezone: Any = None,
    gemini_api_key: str | None = None,
    model: str | None = None,
    resume: bool = True,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Proxy to :func:`egregora.pipeline.process_whatsapp_export` without eager imports."""

    process = cast(
        _ProcessWhatsAppExport,
        getattr(
            import_module("egregora.pipeline"),
            "process_whatsapp_export",
        ),
    )

    return process(
        zip_path=zip_path,
        output_dir=output_dir,
        period=period,
        enable_enrichment=enable_enrichment,
        from_date=from_date,
        to_date=to_date,
        timezone=timezone,
        gemini_api_key=gemini_api_key,
        model=model,
        resume=resume,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
    )
