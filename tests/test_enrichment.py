"""Enrichment system tests using WhatsApp test data."""

from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from egregora.config import EnrichmentConfig
from egregora.enrichment import ContentEnricher, URL_RE, MESSAGE_RE, EnrichmentResult
from egregora.cache_manager import CacheManager
from test_framework.helpers import TestDataGenerator


class MockGeminiClient:
    def __init__(self, relevance=5):
        self.call_count = 0
        self.relevance = relevance

    async def generate_content_async(self, contents, generation_config):
        self.call_count += 1
        response_data = {
            "summary": "Mocked summary",
            "key_points": ["Point 1", "Point 2"],
            "tone": "neutral",
            "relevance": self.relevance,
        }
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.text = json.dumps(response_data)
        mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
        mock_response.text = mock_part.text
        return mock_response


def test_url_extraction_whatsapp_content(tmp_path):
    """Test URL extraction from WhatsApp conversation content using regex."""
    whatsapp_content = """03/10/2025 09:46 - Franklin: https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT
03/10/2025 09:46 - Franklin: Legal esse vídeo
03/10/2025 09:47 - Maria: Também gostei! https://example.com/article"""
    urls = URL_RE.findall(whatsapp_content)
    assert len(urls) == 2
    assert "https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT" in urls
    assert "https://example.com/article" in urls


def test_whatsapp_message_parsing(tmp_path):
    """Test parsing of WhatsApp message format using regex."""
    test_messages = [
        "09:45 - Franklin: Teste de grupo",
        "15:30 - Maria José: Mensagem com nome composto",
        "22:15 - +55 11 99999-9999: Mensagem de número",
    ]
    for message in test_messages:
        match = MESSAGE_RE.match(message)
        assert match
        assert match.group("time") and match.group("sender") and match.group("message")


@pytest.mark.asyncio
async def test_content_enrichment_with_whatsapp_urls(tmp_path):
    """Test content enrichment with URLs from WhatsApp conversations."""
    conversation_with_urls = TestDataGenerator.create_complex_conversation()
    config = EnrichmentConfig(enabled=True, max_concurrent_analyses=2)
    cache_manager = CacheManager(tmp_path / "cache")
    mock_client = MockGeminiClient()

    enricher = ContentEnricher(config, cache_manager=cache_manager)
    result = await enricher.enrich([(date.today(), conversation_with_urls)], client=mock_client)

    assert isinstance(result, EnrichmentResult)
    assert len(result.items) >= 1
    assert result.items[0].analysis is not None
    assert result.items[0].analysis.summary == "Mocked summary"


@pytest.mark.asyncio
async def test_enrichment_caching_functionality(tmp_path):
    """Test that enrichment results are properly cached."""
    test_url = "https://example.com/test-article"
    transcript = [(date.today(), f"Check this out: {test_url}")]
    config = EnrichmentConfig(enabled=True)
    cache_manager = CacheManager(tmp_path / "cache")
    mock_client = MockGeminiClient()

    enricher = ContentEnricher(config, cache_manager=cache_manager)

    # First call should hit the API
    await enricher.enrich(transcript, client=mock_client)
    assert mock_client.call_count == 1

    # Second call should use cache
    await enricher.enrich(transcript, client=mock_client)
    assert mock_client.call_count == 1


@pytest.mark.asyncio
async def test_media_placeholder_handling(tmp_path):
    """Test handling of media placeholders in WhatsApp content."""
    content_with_media = "09:46 - Franklin: <mídia oculta>"
    config = EnrichmentConfig(enabled=True)
    enricher = ContentEnricher(config)
    result = await enricher.enrich([(date.today(), content_with_media)], client=None)

    assert isinstance(result, EnrichmentResult)
    assert len(result.items) == 1
    assert result.items[0].reference.is_media_placeholder
    assert "Mídia sem descrição" in result.items[0].analysis.summary


@pytest.mark.asyncio
async def test_enrichment_with_disabled_config(tmp_path):
    """Test that enrichment is skipped when disabled in config."""
    conversation = TestDataGenerator.create_complex_conversation()
    config = EnrichmentConfig(enabled=False)
    enricher = ContentEnricher(config)
    result = await enricher.enrich([(date.today(), conversation)], client=None)
    assert isinstance(result, EnrichmentResult)
    assert len(result.items) == 0


@pytest.mark.asyncio
async def test_error_handling_in_enrichment(tmp_path):
    """Test error handling during enrichment process."""
    config = EnrichmentConfig(enabled=True)
    transcript = [(date.today(), "https://example.com/failing-url")]

    mock_client = AsyncMock()
    mock_client.generate_content_async.side_effect = Exception("API Error")

    enricher = ContentEnricher(config)
    result = await enricher.enrich(transcript, client=mock_client)

    assert len(result.errors) == 1
    assert "API Error" in result.errors[0]


@pytest.mark.asyncio
async def test_concurrent_url_processing(tmp_path):
    """Test concurrent processing of multiple URLs."""
    content = "https://a.com\nhttps://b.com\nhttps://c.com"
    config = EnrichmentConfig(enabled=True, max_concurrent_analyses=3)
    mock_client = MockGeminiClient()
    enricher = ContentEnricher(config)
    result = await enricher.enrich([(date.today(), content)], client=mock_client)
    assert len(result.items) == 3
    assert mock_client.call_count == 3


@pytest.mark.asyncio
async def test_relevance_filtering(tmp_path):
    """Test filtering of results based on relevance scores."""
    config = EnrichmentConfig(enabled=True, relevance_threshold=6)
    content = "https://low.com\nhttps://high.com"

    class VarRelevanceClient:
        def __init__(self):
            self.calls = 0
        async def generate_content_async(self, contents, generation_config):
            self.calls += 1
            prompt_text = contents[0].parts[0].text
            # Check for the specific URL in the prompt, not just substring
            relevance = 5 if '"url": "https://low.com"' in prompt_text else 8
            response_data = {"summary": "s", "key_points": [], "tone": "t", "relevance": relevance}
            mock_response = MagicMock()
            mock_part = MagicMock()
            mock_part.text = json.dumps(response_data)
            mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
            mock_response.text = mock_part.text
            return mock_response

    mock_client = VarRelevanceClient()
    enricher = ContentEnricher(config)
    result = await enricher.enrich([(date.today(), content)], client=mock_client)
    
    assert len(result.items) == 2
    relevant_items = result.relevant_items(config.relevance_threshold)
    assert len(relevant_items) == 1
    assert relevant_items[0].analysis.relevance >= 6


if __name__ == "__main__":
    # Manual test runner
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        
        print("Running enrichment tests...")
        
        try:
            test_url_extraction_whatsapp_content(temp_dir)
            print("✓ URL extraction test passed")
            
            test_whatsapp_message_parsing(temp_dir)
            print("✓ Message parsing test passed")
            
            test_content_enrichment_with_whatsapp_urls(temp_dir)
            print("✓ Content enrichment test passed")
            
            test_enrichment_caching_functionality(temp_dir)
            print("✓ Caching test passed")
            
            test_media_placeholder_handling(temp_dir)
            print("✓ Media placeholder test passed")
            
            test_enrichment_with_disabled_config(temp_dir)
            print("✓ Disabled config test passed")
            
            test_error_handling_in_enrichment(temp_dir)
            print("✓ Error handling test passed")
            
            test_concurrent_url_processing(temp_dir)
            print("✓ Concurrent processing test passed")
            
            test_relevance_filtering(temp_dir)
            print("✓ Relevance filtering test passed")
            
            print("\n🎉 All enrichment tests passed!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()