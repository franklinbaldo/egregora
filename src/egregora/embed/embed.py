"""Core logic for generating embeddings using the Gemini API."""

from __future__ import annotations

import polars as pl
import google.generativeai as genai


def get_embedding(text: str, model: str = "models/embedding-001") -> list[float]:
    """
    Generates an embedding for a single piece of text using the Gemini API.
    """
    return genai.embed_content(model=model, content=text)["embedding"]


def embed_dataframe(
    df: pl.DataFrame,
    text_column: str = "message",
    model: str = "models/embedding-001",
    batch_size: int = 10,
) -> pl.DataFrame:
    """
    Generates embeddings for a DataFrame column and adds them as a new 'vector' column.

    Handles batching and chunking of long messages.
    """

    def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
        """Generates embeddings for a batch of texts."""
        results = []
        for text in texts:
            # Simple chunking for long messages
            if len(text) > 2048:
                chunks = [text[i : i + 2048] for i in range(0, len(text), 2048)]
                chunk_embeddings = [get_embedding(chunk, model) for chunk in chunks]
                # Average the embeddings of the chunks
                avg_embedding = [
                    sum(col) / len(col) for col in zip(*chunk_embeddings)
                ]
                results.append(avg_embedding)
            else:
                results.append(get_embedding(text, model))
        return results

    # Process in batches
    vectors = []
    for i in range(0, len(df), batch_size):
        batch_texts = df[i : i + batch_size][text_column].to_list()
        vectors.extend(get_embeddings_batch(batch_texts))

    return df.with_columns(pl.Series(name="vector", values=vectors))


def export_dataframe_to_parquet(df: pl.DataFrame, output_path: str):
    """Exports a DataFrame to a Parquet file."""
    df.write_parquet(output_path)
