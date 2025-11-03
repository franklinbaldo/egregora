"""Orchestration - Pipeline coordination and CLI interface.

This package coordinates the entire pipeline execution:
- CLI commands and argument parsing
- Pipeline stage orchestration
- Logging configuration
"""

from .cli import main as cli_main
from .pipeline import process_whatsapp_export

__all__ = [
    "process_whatsapp_export",
    "cli_main",
]
