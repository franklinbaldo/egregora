"""Enrichment system tests using WhatsApp test data."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from egregora.config import EnrichmentConfig
from egregora.enrichment import (
    ContentEnricher,
    URL_RE,
    MESSAGE_RE,
    EnrichmentResult,
    AnalysisResult,
    ContentReference,
)
from egregora.cache_manager import CacheManager
from test_framework.helpers import TestDataGenerator


def create_mock_response(summary, key_points, tone, relevance):
    return Mock(
        text=json.dumps(
            {
                "summary": summary,
                "key_points": key_points,
                "tone": tone,
                "relevance": relevance,
            }
        )
    )


@pytest.fixture
def mock_client():
    client = Mock()
    client.generate_content.return_value = create_mock_response("Summary", ["Point 1"], "neutral", 4)
    return client


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
        assert match is not None


@pytest.mark.asyncio
async def test_content_enrichment_with_whatsapp_urls(tmp_path, mock_client):
    """Test content enrichment with URLs from WhatsApp conversations."""
    conversation_with_urls = TestDataGenerator.create_complex_conversation()
    config = EnrichmentConfig(enabled=True, max_concurrent_analyses=2)
    cache_manager = CacheManager(tmp_path / "cache")
    enricher = ContentEnricher(config, cache_manager=cache_manager)
    
    mock_response = create_mock_response("Summary", ["Point 1"], "neutral", 4)
    with patch('egregora.enrichment.asyncio.to_thread', return_value=mock_response) as mock_to_thread:
        result = await enricher.enrich([(date.today(), conversation_with_urls)], client=mock_client)
        assert mock_to_thread.call_count > 0

    assert isinstance(result, EnrichmentResult)
    assert len(result.items) >= 1
    assert result.items[0].analysis is not None
    assert len(result.items[0].analysis.key_points) >= 1


@pytest.mark.asyncio
async def test_enrichment_caching_functionality(tmp_path, mock_client):
    """Test that enrichment results are properly cached."""
    test_url = "https://example.com/test-article"
    content = f"check this out: {test_url}"
    config = EnrichmentConfig(enabled=True)
    cache_manager = CacheManager(tmp_path / "cache")
    enricher = ContentEnricher(config, cache_manager=cache_manager)

    mock_response = create_mock_response("Summary", ["Point 1"], "neutral", 4)

    # First call, should call API
    with patch('egregora.enrichment.asyncio.to_thread', return_value=mock_response) as mock_to_thread:
        await enricher.enrich([(date.today(), content)], client=mock_client)
        assert mock_to_thread.call_count == 1

    # Second call, should use cache
    with patch('egregora.enrichment.asyncio.to_thread', return_value=mock_response) as mock_to_thread:
        await enricher.enrich([(date.today(), content)], client=mock_client)
        assert mock_to_thread.call_count == 0


@pytest.mark.asyncio
async def test_media_placeholder_handling(tmp_path, mock_client):
    """Test handling of media placeholders in WhatsApp content."""
    content_with_media = "09:46 - Franklin: <mídia oculta>"
    config = EnrichmentConfig(enabled=True)
    cache_manager = CacheManager(tmp_path / "cache")
    enricher = ContentEnricher(config, cache_manager=cache_manager)
    result = await enricher.enrich([(date.today(), content_with_media)], client=mock_client)
    assert isinstance(result, EnrichmentResult)
    assert len(result.items) == 1
    assert result.items[0].analysis.summary is not None


@pytest.mark.asyncio
async def test_enrichment_with_disabled_config(tmp_path):
    """Test that enrichment is skipped when disabled in config."""
    config = EnrichmentConfig(enabled=False)
    enricher = ContentEnricher(config)
    result = await enricher.enrich([], client=None)
    assert len(result.items) == 0


@pytest.mark.asyncio
async def test_error_handling_in_enrichment(tmp_path, mock_client):
    """Test error handling during enrichment process."""
    config = EnrichmentConfig(enabled=True)
    reference = ContentReference(date.today(), "http://test.com", "Test", "12:00", "test", [], [])
    enricher = ContentEnricher(config)
    
    with patch('egregora.enrichment.asyncio.to_thread', side_effect=Exception("API Error")) as mock_to_thread:
        result = await enricher._analyze_reference(reference, mock_client)
        assert mock_to_thread.call_count == 1
    
    assert isinstance(result, AnalysisResult)
    assert result.error == "API Error"
    assert not result.is_successful


@pytest.mark.asyncio
async def test_concurrent_url_processing(tmp_path, mock_client):
    """Test concurrent processing of multiple URLs."""
    content = "https://a.com\nhttps://b.com\nhttps://c.com"
    config = EnrichmentConfig(enabled=True, max_concurrent_analyses=3)
    enricher = ContentEnricher(config)
    
    mock_response = create_mock_response("Summary", [], "neutral", 4)
    with patch('egregora.enrichment.asyncio.to_thread', return_value=mock_response) as mock_to_thread:
        result = await enricher.enrich([(date.today(), content)], client=mock_client)
        assert mock_to_thread.call_count == 3
    
    assert len(result.items) == 3


@pytest.mark.asyncio
async def test_relevance_filtering(tmp_path, mock_client):
    """Test filtering of results based on relevance scores."""
    config = EnrichmentConfig(enabled=True, relevance_threshold=5)
    enricher = ContentEnricher(config)
    content = "https://low.com\nhttps://high.com"

    def side_effect(func, *args, **kwargs):
        reference = None
        for cell in func.__closure__:
            if isinstance(cell.cell_contents, ContentReference):
                reference = cell.cell_contents
                break
        
        url = reference.url
        relevance = 8 if "high" in url else 4
        return create_mock_response("Summary", [], "neutral", relevance)

    with patch('egregora.enrichment.asyncio.to_thread', side_effect=side_effect) as mock_to_thread:
        result = await enricher.enrich([(date.today(), content)], client=mock_client)
        assert mock_to_thread.call_count == 2

    prompt = result.format_for_prompt(config.relevance_threshold)
    assert prompt is not None
    assert "URL: https://low.com" not in prompt
    assert "URL: https://high.com" in prompt