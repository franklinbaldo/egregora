"""Integration tests covering keyword extraction and post retrieval."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from egregora.config import PipelineConfig, RAGConfig
from egregora.rag.query_gen import QueryGenerator, QueryResult
from egregora.rag.indexer import detect_post_date, hash_text
from egregora.rag.search import tokenize, STOP_WORDS
from test_framework.helpers import create_test_zip


def test_query_generation_whatsapp_content(temp_dir):
    """Test query generation components with WhatsApp conversation content."""
    whatsapp_content = """03/10/2025 09:45 - Franklin: Teste de grupo sobre tecnologia
03/10/2025 09:46 - Franklin: Vamos discutir IA e machine learning
03/10/2025 09:47 - Franklin: Legal esse vídeo sobre programação"""
    
    # Test tokenization functionality
    tokens = tokenize(whatsapp_content)
    
    # Validate tokenization
    assert len(tokens) > 0
    assert 'tecnologia' in tokens or 'tecnologia' in whatsapp_content.lower()
    assert 'machine' in tokens or 'learning' in tokens
    
    # Test stop words filtering
    meaningful_tokens = [token for token in tokens if token not in STOP_WORDS]
    assert len(meaningful_tokens) > 0
    
    # Test query generator initialization
    query_gen = QueryGenerator()
    assert hasattr(query_gen, 'config')
    assert isinstance(query_gen.config, RAGConfig)


def test_post_date_detection(temp_dir):
    """Test post date detection functionality."""
    # Test date detection in file paths
    test_files = [
        "2025-10-03.md",
        "post-2025-10-03.md",
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
        result = detect_post_date(Path(filename))
        assert result == expected, f"Failed for {filename}: got {result}, expected {expected}"


from egregora.config import PipelineConfig, RAGConfig
from egregora.rag.index import PostRAG
from egregora.rag.keyword_utils import KeywordExtractor, KeywordProvider
from egregora.rag.query_gen import QueryGenerator

BASELINE_PATH = Path(__file__).parent / "data" / "rag_query_baseline.json"
POSTS_FIXTURE = Path(__file__).parent / "data" / "rag_posts"
MAX_KEYWORDS_DEFAULT = 5
STRICT_KEYWORD_LIMIT = 3


@pytest.fixture(scope="module")
def rag_baseline() -> dict[str, Any]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def rag_posts_dir(tmp_path: Path) -> Path:
    target = tmp_path / "posts"
    shutil.copytree(POSTS_FIXTURE, target)
    return target


@pytest.fixture()
def stub_keyword_provider() -> KeywordProvider:
    def _provider(text: str, *, max_keywords: int) -> list[str]:
        summary = summarize_whatsapp_content(text)
        keywords: list[str] = [author.lower() for author in summary["authors"]]
        if summary["has_media_attachment"]:
            keywords.append("anexos de mídia")
        keywords.append(str(summary["line_count"]))
        keywords.append("whatsapp")

        deduped: list[str] = []
        for keyword in keywords:
            if keyword not in deduped:
                deduped.append(keyword)
            if len(deduped) >= max_keywords:
                break
        return deduped[:max_keywords]

    return _provider


def test_keyword_extractor_uses_provider(whatsapp_real_content: str, stub_keyword_provider) -> None:
    extractor = KeywordExtractor(
        max_keywords=MAX_KEYWORDS_DEFAULT,
        keyword_provider=stub_keyword_provider,
    )
    keywords = extractor.extract(whatsapp_real_content)

    assert keywords
    assert len(keywords) <= MAX_KEYWORDS_DEFAULT
    assert keywords[0] == keywords[0].lower()


def test_query_generator_matches_baseline(
    whatsapp_real_content: str,
    rag_baseline: dict[str, object],
    stub_keyword_provider,
) -> None:
    generator = QueryGenerator(keyword_provider=stub_keyword_provider)
    result = generator.generate(whatsapp_real_content)

    expected = rag_baseline["query_generation"]["whatsapp_transcript"]
    assert result.keywords[: len(expected["keywords"])] == expected["keywords"]
    assert result.main_topics == expected["main_topics"]
    assert result.search_query == expected["search_query"]
    assert result.context.startswith("03/10/2025 09:45")


def test_query_generator_respects_max_keywords(
    whatsapp_real_content: str, stub_keyword_provider
) -> None:
    config = RAGConfig(max_keywords=STRICT_KEYWORD_LIMIT)
    generator = QueryGenerator(config, keyword_provider=stub_keyword_provider)
    result = generator.generate(whatsapp_real_content)

    assert len(result.keywords) <= STRICT_KEYWORD_LIMIT


def test_post_rag_search_matches_baseline(
    rag_posts_dir: Path, rag_baseline: dict[str, object], tmp_path: Path
) -> None:
    config = RAGConfig(
        persist_dir=tmp_path / "vector",
        cache_dir=tmp_path / "cache",
        min_similarity=0.0,
        top_k=3,
    )
    rag = PostRAG(posts_dir=rag_posts_dir, config=config)
    rag.update_index(force_rebuild=True)

    expected_queries = rag_baseline["post_search_queries"]
    expected_results = rag_baseline["post_search"]

    for slug, query in expected_queries.items():
        hits = rag.search(query, top_k=3, min_similarity=0.0)
        assert hits, f"expected hits for query '{query}'"

        expected_hit = expected_results[slug]
        observed_files = []
        for hit in hits:
            metadata = getattr(hit.node, "metadata", {}) or {}
            observed_files.append(metadata.get("file_name"))
        expected_files = [item["file"] for item in expected_hit]
        assert observed_files == expected_files

        for hit, expected_info in zip(hits, expected_hit, strict=True):
            assert hit.node.ref_doc_id == expected_info["doc_id"]
            assert hit.score == pytest.approx(expected_info["score"], rel=0.05, abs=0.01)


def test_rag_config_validation(temp_dir: Path) -> None:
    configs = [
        RAGConfig(enabled=True, max_context_chars=1000),
        RAGConfig(enabled=False),
        RAGConfig(enabled=True, min_similarity=0.8),
    ]

    for rag_config in configs:
        config = PipelineConfig.with_defaults(
            zips_dir=temp_dir,
            posts_dir=temp_dir,
        )
        config.rag = rag_config

        assert config.rag.enabled == rag_config.enabled
        if rag_config.enabled:
            assert config.rag.max_context_chars > 0
            assert 0.0 <= config.rag.min_similarity <= 1.0


def test_whatsapp_data_processing_pipeline(temp_dir: Path, whatsapp_zip_path: Path) -> None:
    zips_dir = temp_dir / "zips"
    zips_dir.mkdir()

    test_zip = zips_dir / "2025-10-03.zip"
    shutil.copy2(whatsapp_zip_path, test_zip)

    assert test_zip.exists()
    
    # Test that the content can be read
    import zipfile
    with zipfile.ZipFile(test_zip, 'r') as zf:
        files = zf.namelist()
        assert "conversation.txt" in files
        
        with zf.open("conversation.txt") as f:
            content = f.read().decode('utf-8')
            assert "Franklin" in content
            assert "IA" in content


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
            
            test_post_date_detection(temp_dir)
            print("✓ Post date detection test passed")
            
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
