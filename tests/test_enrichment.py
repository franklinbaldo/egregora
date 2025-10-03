"""Enrichment system tests using WhatsApp test data."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from egregora.config import EnrichmentConfig
from egregora.enrichment import (
    ContentEnricher,
    URL_RE,
    MESSAGE_RE,
    EnrichmentResult,
)
from egregora.cache_manager import CacheManager
from test_framework.helpers import TestDataGenerator


class MockGeminiClient:
    def __init__(self, relevance=5):
        self.call_count = 0
        self.relevance = relevance
        self.models = self

    def generate_content(self, *args, **kwargs):
        self.call_count += 1
        return Mock(
            text=json.dumps(
                {
                    "summary": "Mock summary",
                    "key_points": ["Point 1", "Point 2"],
                    "tone": "neutral",
                    "relevance": self.relevance,
                }
            )
        )


def test_url_extraction_whatsapp_content():
    """Test URL extraction from WhatsApp conversation content using regex."""
    whatsapp_content = """03/10/2025 09:46 - Franklin: https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT
03/10/2025 09:46 - Franklin: Legal esse vídeo
03/10/2025 09:47 - Maria: Também gostei! https://example.com/article"""
    urls = URL_RE.findall(whatsapp_content)
    assert len(urls) == 2
    assert "https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT" in urls
    assert "https://example.com/article" in urls


def test_whatsapp_message_parsing():
    """Test parsing of WhatsApp message format using regex."""
    test_messages = [
        "09:45 - Franklin: Teste de grupo",
        "15:30 - Maria José: Mensagem com nome composto",
        "22:15 - +55 11 99999-9999: Mensagem de número",
    ]
    for message in test_messages:
        match = MESSAGE_RE.match(message)
        assert match
        assert match.group("time")
        assert match.group("sender")
        assert match.group("message")


def test_content_enrichment_with_whatsapp_urls(temp_dir):
    """Test content enrichment with URLs from WhatsApp conversations."""
    conversation_with_urls = TestDataGenerator.create_complex_conversation()
    config = EnrichmentConfig(enabled=True, max_concurrent_analyses=2)
    cache_manager = CacheManager(temp_dir / "cache")
    transcripts = [(date.today(), conversation_with_urls)]

    with patch("egregora.enrichment.types"):
        mock_client = MockGeminiClient()
        enricher = ContentEnricher(config, cache_manager=cache_manager)
        result = asyncio.run(enricher.enrich(transcripts, client=mock_client))

        assert isinstance(result, EnrichmentResult)
        assert len(result.items) > 0
        assert result.items[0].analysis is not None
        assert result.items[0].analysis.is_successful


def test_enrichment_caching_functionality(temp_dir):
    """Test that enrichment results are properly cached."""
    conversation = "09:45 - Franklin: https://example.com/test-article"
    transcripts = [(date.today(), conversation)]
    config = EnrichmentConfig(enabled=True)
    cache_manager = CacheManager(temp_dir / "cache")

    with patch("egregora.enrichment.types"):
        mock_client = MockGeminiClient()
        enricher = ContentEnricher(config, cache_manager=cache_manager)

        # First call should hit the API
        result1 = asyncio.run(enricher.enrich(transcripts, client=mock_client))
        assert mock_client.call_count == 1
        assert result1.items[0].analysis is not None

        # Second call should use cache
        result2 = asyncio.run(enricher.enrich(transcripts, client=mock_client))
        assert mock_client.call_count == 1  # No additional calls
        assert result2.items[0].analysis is not None
        assert result1.items[0].analysis.summary == result2.items[0].analysis.summary


def test_media_placeholder_handling(temp_dir):
    """Test handling of media placeholders in WhatsApp content."""
    content_with_media = """09:45 - Franklin: Olha essa foto
09:46 - Franklin: <mídia oculta>
09:47 - Franklin: Que acham?"""
    transcripts = [(date.today(), content_with_media)]
    config = EnrichmentConfig(enabled=True)
    cache_manager = CacheManager(temp_dir / "cache")

    enricher = ContentEnricher(config, cache_manager=cache_manager)
    result = asyncio.run(enricher.enrich(transcripts, client=Mock()))

    assert isinstance(result, EnrichmentResult)
    assert len(result.items) == 1
    assert result.items[0].reference.is_media_placeholder


def test_enrichment_with_disabled_config(temp_dir):
    """Test that enrichment is skipped when disabled in config."""
    conversation = TestDataGenerator.create_complex_conversation()
    transcripts = [(date.today(), conversation)]
    config = EnrichmentConfig(enabled=False)  # Disabled
    cache_manager = CacheManager(temp_dir / "cache")
    enricher = ContentEnricher(config, cache_manager=cache_manager)

    result = asyncio.run(enricher.enrich(transcripts, client=None))

    assert isinstance(result, EnrichmentResult)
    assert len(result.items) == 0


def test_error_handling_in_enrichment(temp_dir):
    """Test error handling during enrichment process."""
    conversation = "09:45 - Franklin: https://example.com/failing-url"
    transcripts = [(date.today(), conversation)]
    config = EnrichmentConfig(enabled=True)
    cache_manager = CacheManager(temp_dir / "cache")

    with patch("egregora.enrichment.types"):
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("API Error")
        enricher = ContentEnricher(config, cache_manager=cache_manager)

        result = asyncio.run(enricher.enrich(transcripts, client=mock_client))

        assert isinstance(result, EnrichmentResult)
        assert len(result.items) == 1
        assert result.items[0].analysis is None
        assert result.items[0].error == "API Error"
        assert len(result.errors) == 1


def test_concurrent_url_processing(temp_dir):
    """Test concurrent processing of multiple URLs."""
    content = """09:45 - Franklin: https://example.com/link1
09:46 - Franklin: https://example.com/link2
09:47 - Franklin: https://example.com/link3"""
    transcripts = [(date.today(), content)]
    config = EnrichmentConfig(enabled=True, max_concurrent_analyses=3)
    cache_manager = CacheManager(temp_dir / "cache")

    with patch("egregora.enrichment.types"):
        mock_client = MockGeminiClient()
        enricher = ContentEnricher(config, cache_manager=cache_manager)
        result = asyncio.run(enricher.enrich(transcripts, client=mock_client))

        assert len(result.items) == 3
        assert mock_client.call_count == 3


def test_relevance_filtering(temp_dir):
    """Test filtering of results based on relevance scores."""
    config = EnrichmentConfig(enabled=True, relevance_threshold=4)
    cache_manager = CacheManager(temp_dir / "cache")
    content = """09:45 - Franklin: https://example.com/low-relevance
09:46 - Franklin: https://example.com/high-relevance"""
    transcripts = [(date.today(), content)]

    class VariableRelevanceClient:
        def __init__(self):
            self.call_count = 0
            self.models = self

        def generate_content(self, *args, **kwargs):
            self.call_count += 1
            # This is fragile, but for a test with two items, one will be 3 and one will be 5.
            # The order is not guaranteed by gather, but for the purpose of the test
            # (that one is filtered and one is not), this should be sufficient.
            relevance = 3 if self.call_count % 2 != 0 else 5
            return Mock(
                text=json.dumps(
                    {
                        "summary": "Summary",
                        "key_points": [],
                        "tone": "neutral",
                        "relevance": relevance,
                    }
                )
            )

    with patch("egregora.enrichment.types"):
        mock_client = VariableRelevanceClient()
        enricher = ContentEnricher(config, cache_manager=cache_manager)
        result = asyncio.run(enricher.enrich(transcripts, client=mock_client))

        relevant_items = result.relevant_items(config.relevance_threshold)
        assert len(result.items) == 2
        assert len(relevant_items) == 1
        assert relevant_items[0].analysis.relevance == 5