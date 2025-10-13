"""Gemini-based embedding generation."""

from __future__ import annotations
import os
from typing import Iterable
import numpy as np
import polars as pl
import google.generativeai as genai

MODEL_NAME = "models/embedding-001"
CHUNK_SIZE = 2048  # As per the plan's suggestion for long messages

_api_key_configured = False

def _configure_api_key():
    """Configure the Gemini API key from environment variables."""
    global _api_key_configured
    if _api_key_configured:
        return

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)
    _api_key_configured = True


def get_embedding(text: str | list[str]) -> list[float] | list[list[float]]:
    """Generates an embedding for a given text or list of texts."""
    _configure_api_key()
    if isinstance(text, str):
        # Handle chunking for single long strings
        if len(text) > CHUNK_SIZE:
            chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
            embeddings = genai.embed_content(model=MODEL_NAME, content=chunks)["embedding"]
            return np.mean(embeddings, axis=0).tolist()
        else:
            return genai.embed_content(model=MODEL_NAME, content=text)["embedding"]
    else:
        # Batch embedding for a list of strings
        result = genai.embed_content(model=MODEL_NAME, content=text)
        return result["embedding"]


def embed_dataframe(df: pl.DataFrame, batch_size: int = 10) -> pl.DataFrame:
    """Adds a 'vector' column to the DataFrame with Gemini embeddings."""
    if "message" not in df.columns:
        raise ValueError("DataFrame must contain a 'message' column.")

    messages = df["message"].to_list()
    all_embeddings = []

    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        batch_embeddings = get_embedding(batch)
        all_embeddings.extend(batch_embeddings)

    return df.with_columns(pl.Series(name="vector", values=all_embeddings))


def export_to_parquet(df: pl.DataFrame, path: str) -> None:
    """Exports the DataFrame to a Parquet file."""
    df.write_parquet(path)
