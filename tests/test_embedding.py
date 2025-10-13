"""Tests for the embedding module."""

from __future__ import annotations

import polars as pl
import pytest
from unittest.mock import patch

from egregora.embed.embed import embed_dataframe, get_embedding


@pytest.fixture
def mock_gemini_embed():
    """Mocks the Gemini API embed_content function."""
    with patch("google.generativeai.embed_content") as mock:
        mock.return_value = {"embedding": [0.1] * 768}
        yield mock


def test_get_embedding(mock_gemini_embed):
    """Tests that get_embedding returns a vector of the correct dimension."""
    embedding = get_embedding("test text")
    assert isinstance(embedding, list)
    assert len(embedding) == 768
    mock_gemini_embed.assert_called_once_with(
        model="models/embedding-001", content="test text"
    )


def test_embed_dataframe(mock_gemini_embed):
    """Tests that embed_dataframe adds a 'vector' column with the correct dimensions."""
    df = pl.DataFrame({"message": ["test 1", "test 2"]})
    embedded_df = embed_dataframe(df)

    assert "vector" in embedded_df.columns
    assert embedded_df["vector"].dtype == pl.List(pl.Float64)
    assert len(embedded_df["vector"][0]) == 768
    assert len(embedded_df["vector"][1]) == 768
    assert mock_gemini_embed.call_count == 2


def test_embed_dataframe_with_chunking(mock_gemini_embed):
    """Tests that long messages are chunked and their embeddings are averaged."""
    long_message = "a" * 3000
    df = pl.DataFrame({"message": [long_message]})

    # The mock will return the same embedding for each chunk
    embedded_df = embed_dataframe(df)

    assert "vector" in embedded_df.columns
    assert len(embedded_df["vector"][0]) == 768
    # Two chunks: one of 2048 and one of 952
    assert mock_gemini_embed.call_count == 2
