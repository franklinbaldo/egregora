"""Pipeline orchestration - CLI and main processing workflows.

This package coordinates the ETL pipeline execution.
"""

from .cli import main as cli_main
from .pipeline import process_whatsapp_export

__all__ = [
    "process_whatsapp_export",
    "cli_main",
]
