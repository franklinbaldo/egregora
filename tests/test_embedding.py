"""Tests for the Gemini embedding logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import polars as pl
import pytest

from egregora.embed.embed import (
    CHUNK_SIZE,
    MODEL_NAME,
    embed_dataframe,
    export_to_parquet,
    get_embedding,
)

DIMENSION = 768  # Standard for embedding-001

@pytest.fixture(autouse=True)
def mock_api_key_check():
    """Fixture to bypass the API key check during tests."""
    with patch("egregora.embed.embed._configure_api_key") as mock_configure:
        yield mock_configure

@pytest.fixture
def mock_genai():
    """Fixture to mock the google.generativeai client."""
    with patch("egregora.embed.embed.genai") as mock_genai_client:
        yield mock_genai_client


def test_get_embedding_single_string(mock_genai):
    """Test embedding a single short string."""
    text = "This is a test."
    mock_embedding = np.random.rand(DIMENSION).tolist()
    mock_genai.embed_content.return_value = {"embedding": mock_embedding}

    embedding = get_embedding(text)

    assert isinstance(embedding, list)
    assert len(embedding) == DIMENSION
    mock_genai.embed_content.assert_called_once_with(model=MODEL_NAME, content=text)


def test_get_embedding_long_string_chunks(mock_genai):
    """Test that a long string is correctly chunked and embeddings are averaged."""
    long_text = "a" * (CHUNK_SIZE * 2 + 100)
    num_chunks = 3

    # Set up the mock to return predictable embeddings for averaging
    np.random.seed(0)
    mock_embeddings = [np.random.rand(DIMENSION) for _ in range(num_chunks)]
    mock_genai.embed_content.return_value = {"embedding": [e.tolist() for e in mock_embeddings]}

    embedding = get_embedding(long_text)

    assert len(embedding) == DIMENSION
    # The final embedding should be the mean of the chunk embeddings
    expected_embedding = np.mean(mock_embeddings, axis=0)
    assert np.allclose(embedding, expected_embedding, atol=1e-6)

    # Check that embed_content was called with the chunks
    call_args = mock_genai.embed_content.call_args[1]
    assert call_args["model"] == MODEL_NAME
    assert isinstance(call_args["content"], list)
    assert len(call_args["content"]) == num_chunks


def test_embed_dataframe(mock_genai):
    """Test the full DataFrame embedding process."""
    df = pl.DataFrame({
        "message": ["Hello world", "This is a test.", "A third message."],
    })

    # Make the mock return embeddings with predictable values
    mock_embeddings = [np.full(DIMENSION, i).tolist() for i in range(len(df))]

    # Since we are batching, the mock needs to handle multiple calls with different inputs
    def mock_embed_side_effect(model, content):
        if content == ["Hello world", "This is a test."]:
            return {"embedding": mock_embeddings[0:2]}
        elif content == ["A third message."]:
            return {"embedding": [mock_embeddings[2]]}
        return {"embedding": []}

    mock_genai.embed_content.side_effect = mock_embed_side_effect

    result_df = embed_dataframe(df, batch_size=2)

    assert "vector" in result_df.columns
    assert result_df.shape == (len(df), df.shape[1] + 1)

    vectors = result_df["vector"].to_list()
    assert len(vectors) == len(df)
    assert len(vectors[0]) == DIMENSION

    # Check if the correct embeddings were added
    for i, vector in enumerate(vectors):
        assert np.allclose(vector, mock_embeddings[i])

    # Check that embed_content was called with the correct batches
    assert mock_genai.embed_content.call_count == 2
    mock_genai.embed_content.assert_any_call(model=MODEL_NAME, content=["Hello world", "This is a test."])
    mock_genai.embed_content.assert_any_call(model=MODEL_NAME, content=["A third message."])


def test_parquet_export_round_trip(tmp_path):
    """Test that a DataFrame with embeddings can be saved and loaded from Parquet."""
    df = pl.DataFrame({
        "message": ["test"],
        "vector": [[0.1, 0.2, 0.3]],
    })

    output_path = tmp_path / "test.parquet"
    export_to_parquet(df, str(output_path))

    assert output_path.exists()

    loaded_df = pl.read_parquet(output_path)

    # Parquet might change the inner list to a numpy array, so we check for equality differently
    assert df["message"].equals(loaded_df["message"])
    assert "vector" in loaded_df.columns
    # Polars < 0.20 reads list[float] as a Series of Series, newer versions as list
    if isinstance(loaded_df["vector"][0], pl.Series):
        assert loaded_df["vector"][0].to_list() == [0.1, 0.2, 0.3]
    else:
        assert isinstance(loaded_df["vector"][0], list)
        assert loaded_df["vector"][0] == [0.1, 0.2, 0.3]
