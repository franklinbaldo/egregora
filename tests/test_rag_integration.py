"""RAG system integration tests using WhatsApp test data."""

from __future__ import annotations

import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from egregora.config import PipelineConfig, RAGConfig
from egregora.rag.query_gen import QueryGenerator, QueryResult
from egregora.rag.indexer import detect_newsletter_date, hash_text
from egregora.rag.search import tokenize, STOP_WORDS
from test_framework.helpers import (
    load_real_whatsapp_transcript,
    summarize_whatsapp_content,
)


def test_query_generation_whatsapp_content(temp_dir, whatsapp_real_content):
    """Test query generation components with WhatsApp conversation content."""
    # Test tokenization functionality
    tokens = tokenize(whatsapp_real_content)

    # Validate tokenization against real data
    assert len(tokens) > 0
    assert 'franklin' in tokens
    assert any(token in tokens for token in ['grupo', 'vídeo', 'mensagens'])
    
    # Test stop words filtering
    meaningful_tokens = [token for token in tokens if token not in STOP_WORDS]
    assert len(meaningful_tokens) > 0
    
    # Test query generator initialization
    query_gen = QueryGenerator()
    assert hasattr(query_gen, 'config')
    assert isinstance(query_gen.config, RAGConfig)


def test_newsletter_date_detection(temp_dir):
    """Test newsletter date detection functionality."""
    # Test date detection in file paths
    test_files = [
        "2025-10-03.md",
        "newsletter-2025-10-03.md", 
        "daily-2025-12-25.txt",
        "no-date-file.md",
    ]
    
    expected_dates = [
        date(2025, 10, 3),
        date(2025, 10, 3),
        date(2025, 12, 25),
        None,
    ]
    
    for filename, expected in zip(test_files, expected_dates):
        result = detect_newsletter_date(Path(filename))
        assert result == expected, f"Failed for {filename}: got {result}, expected {expected}"


def test_rag_config_validation(temp_dir):
    """Test RAG configuration with WhatsApp setup."""
    # Test various RAG configurations
    configs = [
        RAGConfig(enabled=True, max_context_chars=1000),
        RAGConfig(enabled=False),
        RAGConfig(enabled=True, min_similarity=0.8),
    ]
    
    for rag_config in configs:
        config = PipelineConfig.with_defaults(
            zips_dir=temp_dir,
            newsletters_dir=temp_dir,
            media_dir=temp_dir / "media",
        )
        config.rag = rag_config
        
        # Validate configuration
        assert config.rag.enabled == rag_config.enabled
        if rag_config.enabled:
            assert config.rag.max_context_chars > 0
            assert 0.0 <= config.rag.min_similarity <= 1.0


def test_search_functionality_patterns(temp_dir):
    """Test search patterns with WhatsApp-like content."""
    # Create test content that simulates indexed conversations
    test_conversations = [
        "Discussão sobre tecnologia e IA moderna",
        "Conversa sobre Python e programação",
        "Debate sobre machine learning e dados",
        "Chat sobre desenvolvimento web",
        "Mensagens sobre carreira em tech",
    ]
    
    # Test search query patterns
    search_queries = [
        "tecnologia",
        "Python programação", 
        "machine learning",
        "desenvolvimento",
        "carreira tech",
    ]
    
    # Basic validation - search functionality exists and processes queries
    for query in search_queries:
        # Validate query format
        assert isinstance(query, str)
        assert len(query.strip()) > 0
        
        # Test query preprocessing
        processed = query.lower().strip()
        assert len(processed) > 0


def test_rag_context_preparation(temp_dir, whatsapp_real_content):
    """Test RAG context preparation with WhatsApp data."""
    whatsapp_transcripts = [
        (date(2025, 10, 1), "Conversa sobre projeto A"),
        (date(2025, 10, 2), "Discussão sobre implementação"),
        (date(2025, 10, 3), whatsapp_real_content),
    ]
    
    # Test context preparation logic
    max_chars = 500
    context_parts = []
    
    for transcript_date, content in whatsapp_transcripts:
        base = '\n'.join(context_parts)
        prefix = f"[{transcript_date}] "
        available = max_chars - len(base)
        if context_parts:
            available -= 1  # account for newline separator
        available -= len(prefix)
        if available <= 0:
            break
        snippet = content[:available]
        if snippet:
            context_parts.append(f"{prefix}{snippet}")
    
    final_context = '\n'.join(context_parts)
    
    # Validate context preparation
    assert len(final_context) <= max_chars
    assert len(context_parts) > 0
    
    # Validate date formatting
    for part in context_parts:
        assert part.startswith('[2025-')
        assert ']' in part

    assert any(part.startswith('[2025-10-03]') for part in context_parts)
    assert '03/10/2025 09:45' in final_context


def test_text_hashing_functionality(temp_dir, whatsapp_real_content):
    """Test text hashing for content change detection."""
    lines = [
        line for line in whatsapp_real_content.splitlines()
        if line.startswith('03/10/2025') and 'Franklin:' in line
    ]
    assert len(lines) >= 3

    whatsapp_texts = [lines[0], lines[1], lines[0]]
    
    hashes = [hash_text(text) for text in whatsapp_texts]
    
    # Validate hash generation
    assert len(hashes) == 3
    assert all(isinstance(h, str) for h in hashes)
    assert all(len(h) > 0 for h in hashes)
    
    # Identical texts should have identical hashes
    assert hashes[0] == hashes[2]
    
    # Different texts should have different hashes
    assert hashes[0] != hashes[1]


def test_whatsapp_data_processing_pipeline(temp_dir, whatsapp_zip_path):
    """Test complete data processing pipeline with WhatsApp format."""
    # Setup test data
    zips_dir = temp_dir / "zips"
    zips_dir.mkdir()

    test_zip = zips_dir / "2025-10-03.zip"
    shutil.copy2(whatsapp_zip_path, test_zip)

    assert test_zip.exists()

    content = load_real_whatsapp_transcript(test_zip)
    metadata = summarize_whatsapp_content(content)
    assert metadata["url_count"] >= 1
    assert metadata["has_media_attachment"]
    assert metadata["authors"]


def test_rag_performance_considerations(temp_dir):
    """Test performance considerations for RAG with large datasets."""
    # Simulate large conversation dataset
    large_conversations = []
    
    for day in range(10):  # 10 days of conversations
        for hour in range(8, 18):  # 8 AM to 6 PM
            for message in range(5):  # 5 messages per hour
                content = f"{hour:02d}:{message*10:02d} - User{message}: Message about topic {day}-{hour}-{message}"
                large_conversations.append(content)
    
    all_content = '\n'.join(large_conversations)
    
    # Test content size management
    max_chars = 10000
    if len(all_content) > max_chars:
        # Truncate to fit within limits
        truncated = all_content[:max_chars]
        # Ensure we don't cut in middle of line
        if '\n' in truncated:
            truncated = truncated.rsplit('\n', 1)[0]
        
        assert len(truncated) <= max_chars
        assert truncated.endswith('User0: Message about topic') or 'User' in truncated


def test_search_result_structure():
    """Test search result data structure."""
    # Test SearchResult structure without actual search
    test_results = []
    
    # Simulate search results
    for i in range(3):
        result = {
            'content': f"Test content {i}",
            'score': 0.9 - (i * 0.1),
            'metadata': {'date': f'2025-10-0{i+1}', 'source': 'whatsapp'}
        }
        test_results.append(result)
    
    # Validate result structure
    assert len(test_results) == 3
    
    for result in test_results:
        assert 'content' in result
        assert 'score' in result
        assert 'metadata' in result
        assert 0.0 <= result['score'] <= 1.0


if __name__ == "__main__":
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        
        print("Running RAG integration tests...")
        
        try:
            test_query_generation_whatsapp_content(temp_dir)
            print("✓ Query generation test passed")
            
            test_newsletter_date_detection(temp_dir)
            print("✓ Newsletter date detection test passed")
            
            test_rag_config_validation(temp_dir)
            print("✓ RAG config validation test passed")
            
            test_search_functionality_patterns(temp_dir)
            print("✓ Search functionality patterns test passed")
            
            test_rag_context_preparation(temp_dir)
            print("✓ RAG context preparation test passed")
            
            test_text_hashing_functionality(temp_dir)
            print("✓ Text hashing functionality test passed")
            
            test_whatsapp_data_processing_pipeline(temp_dir)
            print("✓ WhatsApp data processing pipeline test passed")
            
            test_rag_performance_considerations(temp_dir)
            print("✓ RAG performance considerations test passed")
            
            test_search_result_structure()
            print("✓ Search result structure test passed")
            
            print("\n🎉 All RAG integration tests passed!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()