"""Tests for RAG embedding strategy pattern (TDD).

Sapper mode: Defensive, methodical, building solid foundations.
"""

import os
from unittest.mock import Mock, patch

import pytest

from egregora.rag.strategies import EmbeddingProviderFactory, EmbeddingStrategy
from egregora.rag.strategies.exceptions import (
    ProviderNotAvailableError,
    UnsupportedModelError,
)


class TestStrategyPattern:
    """Test the strategy pattern abstraction."""

    def test_factory_creates_openrouter_strategy_for_qwen_model(self):
        """Factory should create OpenRouterEmbeddingStrategy for qwen/* models."""
        strategy = EmbeddingProviderFactory.create("qwen/qwen3-embedding-0.6b")
        assert strategy.__class__.__name__ == "OpenRouterEmbeddingStrategy"
        assert strategy.get_dimension() == 512

    def test_factory_creates_gemini_strategy_for_models_prefix(self):
        """Factory should create GeminiEmbeddingStrategy for models/* format."""
        strategy = EmbeddingProviderFactory.create("models/gemini-embedding-001")
        assert strategy.__class__.__name__ == "GeminiEmbeddingStrategy"
        assert strategy.get_dimension() == 768

    def test_factory_raises_unsupported_model_error_for_invalid_format(self):
        """Factory should raise UnsupportedModelError for unrecognized model formats."""
        with pytest.raises(UnsupportedModelError, match="invalid-model"):
            EmbeddingProviderFactory.create("invalid-model")


class TestOpenRouterStrategy:
    """Test OpenRouter embedding strategy."""

    @patch("egregora.llm.providers.openrouter_embedding.httpx.Client")
    def test_openrouter_strategy_embeds_texts(self, mock_client_class):
        """OpenRouter strategy should embed texts via OpenRouter API."""
        # Setup mock
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1] * 512},
                {"embedding": [0.2] * 512},
            ]
        }
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        # Create strategy and embed
        strategy = EmbeddingProviderFactory.create("qwen/qwen3-embedding-0.6b")

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            result = strategy.embed(["text1", "text2"])

        # Verify
        assert len(result) == 2
        assert len(result[0]) == 512
        assert result[0] == [0.1] * 512

    def test_openrouter_strategy_is_available_with_api_key(self):
        """OpenRouter strategy should be available when API key is set."""
        strategy = EmbeddingProviderFactory.create("qwen/qwen3-embedding-0.6b")

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            assert strategy.is_available() is True

    def test_openrouter_strategy_raises_when_embedding_without_api_key(self):
        """OpenRouter strategy should raise ProviderNotAvailableError when embedding without API key."""
        strategy = EmbeddingProviderFactory.create("qwen/qwen3-embedding-0.6b")

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ProviderNotAvailableError, match="OpenRouter.*API key"):
                strategy.embed(["text1"])


class TestGeminiStrategy:
    """Test Gemini embedding strategy."""

    @patch("egregora.rag.embedding_router.get_router")
    def test_gemini_strategy_embeds_texts(self, mock_get_router):
        """Gemini strategy should embed texts via Gemini router."""
        # Setup mock
        mock_router = Mock()
        mock_router.embed.return_value = [[0.1] * 768, [0.2] * 768]
        mock_get_router.return_value = mock_router

        # Create strategy and embed
        strategy = EmbeddingProviderFactory.create("models/gemini-embedding-001")

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            result = strategy.embed(["text1", "text2"])

        # Verify
        assert len(result) == 2
        assert len(result[0]) == 768
        mock_router.embed.assert_called_once_with(["text1", "text2"], task_type="RETRIEVAL_DOCUMENT")

    def test_gemini_strategy_is_available_with_api_key(self):
        """Gemini strategy should be available when API key is set."""
        strategy = EmbeddingProviderFactory.create("models/gemini-embedding-001")

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            assert strategy.is_available() is True

    def test_gemini_strategy_raises_when_embedding_without_api_key(self):
        """Gemini strategy should raise ProviderNotAvailableError when embedding without API key."""
        strategy = EmbeddingProviderFactory.create("models/gemini-embedding-001")

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ProviderNotAvailableError, match="Gemini.*API key"):
                strategy.embed(["text1"])


class TestStrategyIntegration:
    """Test strategy integration with RAG system."""

    def test_strategies_follow_same_interface(self):
        """All strategies should implement the same interface."""
        openrouter = EmbeddingProviderFactory.create("qwen/qwen3-embedding-0.6b")
        gemini = EmbeddingProviderFactory.create("models/gemini-embedding-001")

        # Both should be EmbeddingStrategy instances
        assert isinstance(openrouter, EmbeddingStrategy)
        assert isinstance(gemini, EmbeddingStrategy)

        # Both should have same methods
        assert hasattr(openrouter, "embed")
        assert hasattr(openrouter, "get_dimension")
        assert hasattr(openrouter, "is_available")
        assert hasattr(gemini, "embed")
        assert hasattr(gemini, "get_dimension")
        assert hasattr(gemini, "is_available")
