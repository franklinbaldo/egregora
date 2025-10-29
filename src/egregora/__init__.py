"""Egregora v2: Ultra-simple WhatsApp to blog pipeline."""

from types import SimpleNamespace

import duckdb

if not hasattr(duckdb, "functional"):
    duckdb.functional = SimpleNamespace(ARROW="arrow", NATIVE="native")

from .pipeline import process_whatsapp_export

__version__ = "2.0.0"

__all__ = [
    "process_whatsapp_export",
]
