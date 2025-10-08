"""Enrichment system tests using WhatsApp test data."""

from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from egregora.config import EnrichmentConfig
from egregora.enrichment import ContentEnricher, URL_RE, MESSAGE_RE, EnrichmentResult
from egregora.cache_manager import CacheManager
from test_framework.helpers import TestDataGenerator


class MockGeminiModel:
    def __init__(self, relevance=5, error=None):
        self.call_count = 0
        self.relevance = relevance
        self.error = error

    def generate_content(self, model, contents, config):
        self.call_count += 1
        if self.error:
            raise self.error

        response_data = {
            "summary": "Mocked summary",
            "topics": ["Point 1", "Point 2"],
            "actions": [
                {
                    "description": "Revisar conteúdo compartilhado",
                    "owner": "time",
                }
            ],
        }
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.text = json.dumps(response_data)
        mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
        mock_response.text = mock_part.text
        return mock_response


class MockGeminiClient:
    def __init__(self, relevance=5, error=None):
        self.models = MockGeminiModel(relevance, error)

    @property
    def call_count(self):
        return self.models.call_count

@patch("mimetypes.guess_type", return_value=("text/html", None))
def test_content_enrichment_with_whatsapp_urls(mock_guess_type, tmp_path):
    conversation_with_urls = TestDataGenerator.create_complex_conversation()
    config = EnrichmentConfig(enabled=True, max_concurrent_analyses=2)
    cache_manager = CacheManager(tmp_path / "cache", size_limit_mb=10)
    mock_client = MockGeminiClient()

    enricher = ContentEnricher(config, cache_manager=cache_manager)
    result = asyncio.run(enricher.enrich([(date.today(), conversation_with_urls)], client=mock_client))

    assert isinstance(result, EnrichmentResult)
    assert len(result.items) >= 1
    assert result.items[0].analysis is not None
    assert result.items[0].analysis.summary == "Mocked summary"
    assert result.items[0].analysis.topics == ["Point 1", "Point 2"]
    assert [item.description for item in result.items[0].analysis.actions] == [
        "Revisar conteúdo compartilhado"
    ]

@patch("mimetypes.guess_type", return_value=("text/html", None))
def test_enrichment_caching_functionality(mock_guess_type, tmp_path):
    test_url = "https://example.com/test-article"
    transcript = [(date.today(), f"Check this out: {test_url}")]
    config = EnrichmentConfig(enabled=True)
    cache_manager = CacheManager(tmp_path / "cache", size_limit_mb=10)
    mock_client = MockGeminiClient()

    enricher = ContentEnricher(config, cache_manager=cache_manager)
    asyncio.run(enricher.enrich(transcript, client=mock_client))
    assert mock_client.call_count == 1

    asyncio.run(enricher.enrich(transcript, client=mock_client))
    assert mock_client.call_count == 1

def test_media_placeholder_handling(tmp_path):
    content_with_media = "09:46 - Franklin: <mídia oculta>"
    config = EnrichmentConfig(enabled=True)
    enricher = ContentEnricher(config)
    result = asyncio.run(enricher.enrich([(date.today(), content_with_media)], client=None))

    assert isinstance(result, EnrichmentResult)
    assert len(result.items) == 1
    assert result.items[0].reference.is_media_placeholder
    assert "Mídia sem descrição" in result.items[0].analysis.summary

def test_enrichment_with_disabled_config(tmp_path):
    conversation = TestDataGenerator.create_complex_conversation()
    config = EnrichmentConfig(enabled=False)
    enricher = ContentEnricher(config)
    result = asyncio.run(enricher.enrich([(date.today(), conversation)], client=None))
    assert isinstance(result, EnrichmentResult)
    assert len(result.items) == 0

@patch("mimetypes.guess_type", return_value=("text/html", None))
def test_error_handling_in_enrichment(mock_guess_type, tmp_path):
    config = EnrichmentConfig(enabled=True)
    transcript = [(date.today(), "https://example.com/failing-url")]
    mock_client = MockGeminiClient(error=Exception("API Error"))

    enricher = ContentEnricher(config)
    result = asyncio.run(enricher.enrich(transcript, client=mock_client))

    assert len(result.errors) == 1
    assert "API Error" in result.errors[0]

@patch("mimetypes.guess_type", return_value=("text/html", None))
def test_concurrent_url_processing(mock_guess_type, tmp_path):
    content = "https://a.com\nhttps://b.com\nhttps://c.com"
    config = EnrichmentConfig(enabled=True, max_concurrent_analyses=3)
    mock_client = MockGeminiClient()
    enricher = ContentEnricher(config)
    result = asyncio.run(enricher.enrich([(date.today(), content)], client=mock_client))
    assert len(result.items) == 3
    assert mock_client.call_count == 3

@patch("mimetypes.guess_type", return_value=("text/html", None))
def test_relevance_filtering(mock_guess_type, tmp_path):
    config = EnrichmentConfig(enabled=True, relevance_threshold=3)
    content = "https://low.com\nhttps://high.com"

    class VarRelevanceClient:
        def __init__(self):
            self.models = self
            self.calls = 0
        def generate_content(self, model, contents, config):
            self.calls += 1
            prompt_text = contents[0].parts[0].text
            is_low = '"url": "https://low.com"' in prompt_text
            response_data = {
                "summary": "Resumo",
                "topics": [] if is_low else ["Tema"],
                "actions": [],
            }
            mock_response = MagicMock()
            mock_part = MagicMock()
            mock_part.text = json.dumps(response_data)
            mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
            mock_response.text = mock_part.text
            return mock_response

    mock_client = VarRelevanceClient()
    enricher = ContentEnricher(config)
    result = asyncio.run(enricher.enrich([(date.today(), content)], client=mock_client))

    assert len(result.items) == 2
    relevant_items = result.relevant_items(config.relevance_threshold)
    assert len(relevant_items) == 1
    assert relevant_items[0].analysis.relevance >= 3


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