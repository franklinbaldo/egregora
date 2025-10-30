"""Egregora v2: Ultra-simple WhatsApp to blog pipeline."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, cast

__version__ = "2.0.0"

__all__ = [
    "process_whatsapp_export",
]

_Return = dict[str, dict[str, list[str]]]


class _ProcessWhatsAppExport(Protocol):
    def __call__(
        self,
        zip_path: Path,
        output_dir: Path = ...,
        period: str = ...,
        enable_enrichment: bool = ...,
        from_date: Any = ...,
        to_date: Any = ...,
        timezone: Any = ...,
        gemini_api_key: str | None = ...,
        model: str | None = ...,
        resume: bool = ...,
        retrieval_mode: str = ...,
        retrieval_nprobe: int | None = ...,
        retrieval_overfetch: int | None = ...,
    ) -> _Return: ...


def _load_process_whatsapp_export() -> _ProcessWhatsAppExport:
    module = import_module("egregora.pipeline")
    func = getattr(module, "process_whatsapp_export")
    return cast(_ProcessWhatsAppExport, func)


def process_whatsapp_export(
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
) -> _Return:
    """Proxy for :func:`egregora.pipeline.process_whatsapp_export` with lazy import."""

    impl = _load_process_whatsapp_export()
    return impl(
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
