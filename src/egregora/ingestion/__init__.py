"""Ingestion stage - Parse WhatsApp exports into structured data.

This package handles the initial data extraction from WhatsApp ZIP exports,
converting them into Ibis tables for further processing.
"""

from .parser import parse_whatsapp_export

__all__ = ["parse_whatsapp_export"]
