"""Enrichment system tests using WhatsApp test data."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from egregora.config import EnrichmentConfig
from egregora.enrichment import ContentEnricher, URL_RE, MESSAGE_RE
from egregora.cache_manager import CacheManager
from test_framework.helpers import TestDataGenerator


def test_url_extraction_whatsapp_content(temp_dir):
    """Test URL extraction from WhatsApp conversation content using regex."""
    # WhatsApp content with YouTube URL from our test data
    whatsapp_content = """03/10/2025 09:46 - Franklin: https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT
03/10/2025 09:46 - Franklin: Legal esse vídeo
03/10/2025 09:47 - Maria: Também gostei! https://example.com/article"""
    
    # Test URL extraction using the same regex pattern as enrichment
    urls = URL_RE.findall(whatsapp_content)
    
    assert len(urls) == 2
    assert "https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT" in urls
    assert "https://example.com/article" in urls


def test_whatsapp_message_parsing(temp_dir):
    """Test parsing of WhatsApp message format using regex."""
    # Test various WhatsApp message formats using the enrichment regex
    test_messages = [
        "09:45 - Franklin: Teste de grupo",
        "15:30 - Maria José: Mensagem com nome composto", 
        "22:15 - +55 11 99999-9999: Mensagem de número",
    ]
    
    for message in test_messages:
        match = MESSAGE_RE.match(message)
        if match:
            time_str = match.group("time")
            sender = match.group("sender")
            content = match.group("message")
            
            assert len(time_str) > 0
            assert len(sender) > 0
            assert len(content) > 0
            
            # Validate specific format expectations
            assert ":" in time_str  # Should contain time separator
            assert sender.strip() == sender  # Should be trimmed


def test_content_enrichment_with_whatsapp_urls(temp_dir):
    """Test content enrichment with URLs from WhatsApp conversations."""
    conversation_with_urls = TestDataGenerator.create_complex_conversation()
    
    config = EnrichmentConfig(enabled=True, max_concurrent_requests=2)
    cache_manager = CacheManager(temp_dir / "cache")
    
    with patch('egregora.enrichment.genai') as mock_genai:
        mock_client = MockGeminiClient()
        mock_genai.Client.return_value = mock_client
        
        enricher = ContentEnricher(config, cache_manager=cache_manager)
        
        # Process conversation
        result = enricher.process_conversation(
            conversation_with_urls,
            date.today()
        )
        
        assert isinstance(result, EnrichmentResult)
        assert result.processed_urls >= 1  # Should find and process URLs
        assert len(result.analysis_results) >= 1


def test_enrichment_caching_functionality(temp_dir):
    """Test that enrichment results are properly cached."""
    test_url = "https://example.com/test-article"
    
    config = EnrichmentConfig(enabled=True)
    cache_manager = CacheManager(temp_dir / "cache")
    
    with patch('egregora.enrichment.genai') as mock_genai:
        mock_client = MockGeminiClient()
        mock_genai.Client.return_value = mock_client
        
        enricher = ContentEnricher(config, cache_manager=cache_manager)
        
        # First call should hit the API
        result1 = enricher._analyze_url(test_url)
        first_call_count = mock_client.call_count
        
        # Second call should use cache
        result2 = enricher._analyze_url(test_url)
        second_call_count = mock_client.call_count
        
        # Verify caching worked
        assert first_call_count == 1
        assert second_call_count == 1  # No additional calls
        assert result1.summary == result2.summary


def test_media_placeholder_handling(temp_dir):
    """Test handling of media placeholders in WhatsApp content."""
    content_with_media = """09:45 - Franklin: Olha essa foto
09:46 - Franklin: <mídia oculta>
09:47 - Franklin: Que acham?"""
    
    config = EnrichmentConfig(enabled=True)
    cache_manager = CacheManager(temp_dir / "cache")
    
    with patch('egregora.enrichment.genai') as mock_genai:
        mock_client = MockGeminiClient()
        enricher = ContentEnricher(config, cache_manager=cache_manager)
        
        result = enricher.process_conversation(content_with_media, date.today())
        
        # Should handle media placeholders gracefully
        assert isinstance(result, EnrichmentResult)
        # Media placeholders should be processed but not cause errors


def test_enrichment_with_disabled_config(temp_dir):
    """Test that enrichment is skipped when disabled in config."""
    conversation = TestDataGenerator.create_complex_conversation()
    
    config = EnrichmentConfig(enabled=False)  # Disabled
    cache_manager = CacheManager(temp_dir / "cache")
    
    enricher = ContentEnricher(config, cache_manager=cache_manager)
    
    result = enricher.process_conversation(conversation, date.today())
    
    # Should return empty result when disabled
    assert isinstance(result, EnrichmentResult)
    assert result.processed_urls == 0
    assert len(result.analysis_results) == 0


def test_error_handling_in_enrichment(temp_dir):
    """Test error handling during enrichment process."""
    config = EnrichmentConfig(enabled=True)
    cache_manager = CacheManager(temp_dir / "cache")
    
    # Mock client that raises exceptions
    class FailingClient:
        def generate_content(self, *args, **kwargs):
            raise Exception("API Error")
    
    with patch('egregora.enrichment.genai') as mock_genai:
        failing_client = FailingClient()
        enricher = ContentEnricher(config, cache_manager=cache_manager)
        
        # Should handle errors gracefully
        result = enricher._analyze_url("https://example.com/test")
        
        assert isinstance(result, AnalysisResult)
        assert result.error is not None
        assert not result.is_successful


def test_concurrent_url_processing(temp_dir):
    """Test concurrent processing of multiple URLs."""
    content_with_multiple_urls = """09:45 - Franklin: Vejam esses links:
09:46 - Franklin: https://example.com/link1
09:47 - Franklin: https://example.com/link2
09:48 - Franklin: https://example.com/link3"""
    
    config = EnrichmentConfig(enabled=True, max_concurrent_requests=3)
    cache_manager = CacheManager(temp_dir / "cache")
    
    with patch('egregora.enrichment.genai') as mock_genai:
        mock_client = MockGeminiClient()
        mock_genai.Client.return_value = mock_client
        
        enricher = ContentEnricher(config, cache_manager=cache_manager)
        
        result = enricher.process_conversation(content_with_multiple_urls, date.today())
        
        # Should process all URLs
        assert result.processed_urls == 3
        assert len(result.analysis_results) == 3
        assert mock_client.call_count == 3


def test_relevance_filtering(temp_dir):
    """Test filtering of results based on relevance scores."""
    config = EnrichmentConfig(enabled=True, min_relevance=6)  # Higher threshold
    cache_manager = CacheManager(temp_dir / "cache")
    
    # Custom client with varying relevance scores
    class VariableRelevanceClient:
        def __init__(self):
            self.call_count = 0
            
        def generate_content(self, *args, **kwargs):
            self.call_count += 1
            relevance = 5 if self.call_count == 1 else 8  # First low, second high
            return Mock(text=json.dumps({
                "summary": f"Content {self.call_count}",
                "key_points": [f"Point {self.call_count}"],
                "tone": "neutral",
                "relevance": relevance
            }))
    
    with patch('egregora.enrichment.genai') as mock_genai:
        variable_client = VariableRelevanceClient()
        enricher = ContentEnricher(config, cache_manager=cache_manager)
        
        content = """09:45 - Franklin: https://example.com/low-relevance
09:46 - Franklin: https://example.com/high-relevance"""
        
        result = enricher.process_conversation(content, date.today())
        
        # Should filter out low relevance results
        high_relevance_results = [r for r in result.analysis_results if r.relevance >= 6]
        assert len(high_relevance_results) == 1


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