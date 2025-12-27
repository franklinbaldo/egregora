"""Tests for OpenRouter embedding provider."""

import os
from unittest.mock import Mock, patch

import pytest

from egregora.llm.providers.openrouter_embedding import (
    embed_with_openrouter,
    get_embedding_dimension,
    is_openrouter_embedding_model,
)


class TestModelDetection:
    """Test OpenRouter model format detection."""

    def test_is_openrouter_embedding_model_detects_openrouter_format(self):
        """OpenRouter models have provider/model format."""
        assert is_openrouter_embedding_model("qwen/qwen3-embedding-0.6b") is True
        assert is_openrouter_embedding_model("openai/text-embedding-3-small") is True

    def test_is_openrouter_embedding_model_rejects_gemini_format(self):
        """Gemini models start with models/ prefix."""
        assert is_openrouter_embedding_model("models/gemini-embedding-001") is False

    def test_is_openrouter_embedding_model_rejects_plain_names(self):
        """Plain model names without slashes are not OpenRouter."""
        assert is_openrouter_embedding_model("gemini-embedding-001") is False


class TestEmbeddingDimensions:
    """Test embedding dimension detection."""

    def test_get_embedding_dimension_for_qwen(self):
        """Qwen embedding model has 512 dimensions."""
        assert get_embedding_dimension("qwen/qwen3-embedding-0.6b") == 512

    def test_get_embedding_dimension_for_gemini(self):
        """Gemini embedding model has 768 dimensions."""
        assert get_embedding_dimension("models/gemini-embedding-001") == 768

    def test_get_embedding_dimension_unknown_openrouter_model(self):
        """Unknown OpenRouter models use default 512 dimensions."""
        assert get_embedding_dimension("some-provider/unknown-model") == 512


class TestEmbedWithOpenRouter:
    """Test OpenRouter embedding API calls."""

    def test_embed_with_openrouter_requires_api_key(self):
        """Should raise ValueError if API key is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                embed_with_openrouter(["test text"])

    @patch("egregora.llm.providers.openrouter_embedding.httpx.Client")
    def test_embed_with_openrouter_calls_api(self, mock_client_class):
        """Should make POST request to OpenRouter API."""
        # Setup mock
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1, 0.2, 0.3]},
                {"embedding": [0.4, 0.5, 0.6]},
            ]
        }
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        # Call function
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            result = embed_with_openrouter(["text1", "text2"], model="qwen/qwen3-embedding-0.6b")

        # Verify
        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://openrouter.ai/api/v1/embeddings"
        assert call_args[1]["json"]["model"] == "qwen/qwen3-embedding-0.6b"
        assert call_args[1]["json"]["input"] == ["text1", "text2"]
        assert "Bearer test-key" in call_args[1]["headers"]["Authorization"]

    @patch("egregora.llm.providers.openrouter_embedding.httpx.Client")
    def test_embed_with_openrouter_uses_env_var(self, mock_client_class):
        """Should use OPENROUTER_API_KEY from environment."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1]}]}
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "env-key"}):
            embed_with_openrouter(["text"])

        call_args = mock_client.post.call_args
        assert "Bearer env-key" in call_args[1]["headers"]["Authorization"]
