"""Embedding subsystem for Gemini vector generation."""

from .cli import embed_app, register_embed_command
from .embed import EmbeddingResult, GeminiEmbedder

__all__ = ["EmbeddingResult", "GeminiEmbedder", "embed_app", "register_embed_command"]
