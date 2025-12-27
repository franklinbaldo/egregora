"""Tests for Jina AI embedding provider."""

import os
from unittest.mock import Mock, patch

import pytest

from egregora.llm.providers.jina_embedding import (
    embed_with_jina,
    get_embedding_dimension,
    is_jina_embedding_model,
)


class TestModelDetection:
    """Test Jina model format detection."""

    def test_is_jina_embedding_model_detects_jina_format(self):
        """Jina models have jina-ai/ or jinaai/ prefix."""
        assert is_jina_embedding_model("jina-ai/jina-embeddings-v3") is True
        assert is_jina_embedding_model("jinaai/jina-embeddings-v4") is True
        assert is_jina_embedding_model("jina-embeddings-v3") is True

    def test_is_jina_embedding_model_rejects_other_formats(self):
        """Non-Jina models should be rejected."""
        assert is_jina_embedding_model("models/gemini-embedding-001") is False
        assert is_jina_embedding_model("qwen/qwen3-embedding-0.6b") is False
        assert is_jina_embedding_model("openai/text-embedding-3-small") is False


class TestEmbeddingDimensions:
    """Test dimension mapping for Jina models."""

    def test_get_embedding_dimension_for_jina_v3(self):
        """Jina v3 returns 1024 dimensions."""
        assert get_embedding_dimension("jina-embeddings-v3") == 1024
        assert get_embedding_dimension("jina-ai/jina-embeddings-v3") == 1024

    def test_get_embedding_dimension_for_jina_v4(self):
        """Jina v4 returns 2048 dimensions."""
        assert get_embedding_dimension("jina-embeddings-v4") == 2048
        assert get_embedding_dimension("jinaai/jina-embeddings-v4") == 2048

    def test_get_embedding_dimension_defaults_to_1024(self):
        """Unknown Jina models default to 1024 dimensions."""
        assert get_embedding_dimension("jina-embeddings-v5") == 1024


class TestEmbedWithJina:
    """Test Jina embedding API calls."""

    def test_embed_with_jina_requires_api_key(self):
        """Should raise ValueError if no API key provided."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="JINA_API_KEY"):
                embed_with_jina(["test"])

    @patch("egregora.llm.providers.jina_embedding.httpx.Client")
    def test_embed_with_jina_calls_api(self, mock_client_class):
        """Should call Jina API with correct parameters."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2]}]}
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        result = embed_with_jina(["text1", "text2"], api_key="test-key")

        assert result == [[0.1, 0.2]]
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://api.jina.ai/v1/embeddings"
        assert call_args[1]["json"]["model"] == "jina-embeddings-v3"
        assert call_args[1]["json"]["input"] == ["text1", "text2"]
        assert "Bearer test-key" in call_args[1]["headers"]["Authorization"]

    @patch("egregora.llm.providers.jina_embedding.httpx.Client")
    def test_embed_with_jina_uses_env_var(self, mock_client_class):
        """Should use JINA_API_KEY from environment."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1]}]}
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        with patch.dict(os.environ, {"JINA_API_KEY": "env-key"}):
            embed_with_jina(["text"])

        call_args = mock_client.post.call_args
        assert "Bearer env-key" in call_args[1]["headers"]["Authorization"]

    @patch("egregora.llm.providers.jina_embedding.httpx.Client")
    def test_embed_with_jina_strips_quotes_from_api_key(self, mock_client_class):
        """Should strip quotes from API key (common shell export issue)."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1]}]}
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        # Test with quoted key from environment
        with patch.dict(os.environ, {"JINA_API_KEY": '"quoted-key"'}):
            embed_with_jina(["text"])

        call_args = mock_client.post.call_args
        # Should strip quotes
        assert "Bearer quoted-key" in call_args[1]["headers"]["Authorization"]
        assert 'Bearer "quoted-key"' not in call_args[1]["headers"]["Authorization"]
