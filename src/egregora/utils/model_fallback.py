"""Provides a fallback mechanism for creating LLM models."""

from typing import Any


def create_fallback_model(_model_id: str, *, _use_google_batch: bool = False) -> Any:
    """Creates a fallback model.

    This is a placeholder to resolve import errors in the test environment.
    """
    return None
