"""Egregora v2: Multi-platform chat analysis and blog generation."""

from egregora.orchestration.pipelines.write import process_whatsapp_export

__version__ = "2.0.0"
__all__ = [
    "process_whatsapp_export",
]
