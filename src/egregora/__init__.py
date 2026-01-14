"""Egregora: Multi-platform chat analysis and blog generation."""

from egregora.orchestration.pipelines.write import process_whatsapp_export

__version__ = "3.0.1"
__all__ = [
    "process_whatsapp_export",
]
