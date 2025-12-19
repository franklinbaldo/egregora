"""Model name conversion utilities.

Egregora uses two model naming conventions:
- Pydantic-AI: provider-prefixed IDs like ``google-gla:gemini-flash-latest``.
- google-genai SDK: bare model IDs like ``gemini-flash-latest`` (or ``models/...``).

This module provides a small helper to safely convert when calling the
google-genai SDK directly.
"""

from __future__ import annotations


def to_google_genai_model_name(model: str) -> str:
    """Convert a configured model id to a google-genai SDK compatible id."""
    if not model:
        return model
    if model.startswith("google-gla:"):
        return model.removeprefix("google-gla:")
    return model

