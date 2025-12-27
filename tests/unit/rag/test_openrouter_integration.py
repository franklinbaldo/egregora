"""Tests for OpenRouter integration with RAG embedding router."""

import os
from unittest.mock import Mock, patch

import pytest

from egregora.rag import embed_fn


class TestEmbeddingRouterOpenRouterIntegration:
    """Test that embedding router correctly routes to OpenRouter."""

    @patch("egregora.llm.providers.openrouter_embedding.httpx.Client")
    def test_embed_fn_uses_openrouter_for_qwen_model(self, mock_client_class):
        """embed_fn should route to OpenRouter when model is qwen/..."""
        # Setup mock
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * 512}]  # Qwen uses 512 dims
        }
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        # Call embed_fn with OpenRouter model
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            result = embed_fn(("test text",), model="qwen/qwen3-embedding-0.6b")

        # Verify OpenRouter API was called
        assert len(result) == 1
        assert len(result[0]) == 512  # Qwen dimension
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "openrouter.ai" in call_args[0][0]

    @patch("egregora.rag.embedding_router.EmbeddingRouter.embed")
    def test_embed_fn_uses_gemini_router_for_gemini_model(self, mock_embed):
        """embed_fn should route to Gemini router when model is models/..."""
        mock_embed.return_value = [[0.1] * 768]  # Gemini uses 768 dims

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            result = embed_fn(("test text",), model="models/gemini-embedding-001")

        # Verify Gemini router was used
        assert len(result) == 1
        assert len(result[0]) == 768  # Gemini dimension
        mock_embed.assert_called_once()


class TestEmbeddingDimensionConfiguration:
    """Test that embedding dimensions are correctly configured."""

    def test_get_embedding_dimension_from_config(self):
        """Config helper should return correct dimensions for different models."""
        from egregora.config.settings import get_embedding_dimension

        assert get_embedding_dimension("qwen/qwen3-embedding-0.6b") == 512
        assert get_embedding_dimension("models/gemini-embedding-001") == 768


class TestConfigValidation:
    """Test pydantic config validation for embedding models."""

    def test_config_accepts_gemini_embedding_model(self):
        """Config should accept Gemini format embedding models."""
        from egregora.config.settings import ModelSettings

        config = ModelSettings(embedding="models/gemini-embedding-001")
        assert config.embedding == "models/gemini-embedding-001"

    def test_config_accepts_openrouter_embedding_model(self):
        """Config should accept OpenRouter format embedding models."""
        from egregora.config.settings import ModelSettings

        config = ModelSettings(embedding="qwen/qwen3-embedding-0.6b")
        assert config.embedding == "qwen/qwen3-embedding-0.6b"

    def test_config_rejects_invalid_embedding_model_format(self):
        """Config accepts any string, but factory rejects invalid embedding models at runtime."""
        from egregora.config.settings import ModelSettings
        from egregora.rag.strategies import EmbeddingProviderFactory
        from egregora.rag.strategies.exceptions import UnsupportedModelError

        # Config validation no longer checks embedding format (strategy pattern handles it)
        config = ModelSettings(embedding="invalid-model-name")
        assert config.embedding == "invalid-model-name"

        # Factory validates at runtime
        with pytest.raises(UnsupportedModelError, match="Unsupported embedding model"):
            EmbeddingProviderFactory.create("invalid-model-name")
