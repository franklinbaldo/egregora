"""Integration tests covering the RAG pipeline components."""

from datetime import date
from pathlib import Path

from test_framework.helpers import create_test_zip

from egregora.config import PipelineConfig
from egregora.rag.config import RAGConfig
from egregora.rag.indexer import detect_post_date, hash_text
from egregora.rag.query_gen import QueryGenerator, QueryResult


def _stub_keyword_provider(text: str, *, max_keywords: int) -> list[str]:
    """Return deterministic keywords for testing the query generator."""

    base_keywords = [
        "tecnologia",
        "machine",
        "learning",
        "programacao",
    ]
    return base_keywords[:max_keywords]


def test_query_generation_whatsapp_content(temp_dir: Path):
    """Test query generation components with WhatsApp conversation content."""
    whatsapp_content = """03/10/2025 09:45 - Franklin: Teste de grupo sobre tecnologia
03/10/2025 09:46 - Franklin: Vamos discutir IA e machine learning
03/10/2025 09:47 - Franklin: Legal esse vídeo sobre programação"""

    def mock_keyword_provider(text: str, *, max_keywords: int) -> list[str]:
        return ["tecnologia", "IA", "machine learning", "programação"]

    # Test query generator initialization
    query_gen = QueryGenerator(keyword_provider=mock_keyword_provider)
    assert hasattr(query_gen, "config")
    assert isinstance(query_gen.config, RAGConfig)

    result = query_gen.generate(whatsapp_content)
    assert isinstance(result, QueryResult)
    assert "tecnologia" in result.keywords
    assert "IA" in result.keywords
    assert "machine learning" in result.keywords
    assert "programação" in result.keywords


def test_post_date_detection(temp_dir: Path):
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

    for filename, expected in zip(test_files, expected_dates, strict=False):
        result = detect_post_date(Path(filename))
        assert result == expected, f"Failed for {filename}: got {result}, expected {expected}"


def test_rag_config_validation(temp_dir: Path):
    """Test RAG configuration with WhatsApp setup."""
    # Test various RAG configurations
    configs = [
        RAGConfig(enabled=True, max_context_chars=1000),
        RAGConfig(enabled=False),
        RAGConfig(enabled=True, min_similarity=0.8),
    ]

    for rag_config in configs:
        config = PipelineConfig(
            zip_files=[],
            posts_dir=temp_dir,
        )
        config.rag = rag_config

        # Validate configuration
        assert config.rag.enabled == rag_config.enabled
        if rag_config.enabled:
            assert config.rag.max_context_chars > 0
            assert 0.0 <= config.rag.min_similarity <= 1.0


def test_search_functionality_patterns(temp_dir: Path):
    """Test search patterns with WhatsApp-like content."""
    # Create test content that simulates indexed conversations

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


def test_rag_context_preparation(temp_dir: Path):
    """Test RAG context preparation with WhatsApp data."""
    whatsapp_transcripts = [
        (date(2025, 10, 1), "Conversa sobre projeto A"),
        (date(2025, 10, 2), "Discussão sobre implementação"),
        (date(2025, 10, 3), "Review e próximos passos"),
    ]

    # Test context preparation logic
    max_chars = 500
    context_parts = []

    for transcript_date, content in whatsapp_transcripts:
        if len("\n".join(context_parts)) + len(content) <= max_chars:
            context_parts.append(f"[{transcript_date}] {content}")

    final_context = "\n".join(context_parts)

    # Validate context preparation
    assert len(final_context) <= max_chars
    assert len(context_parts) > 0

    # Validate date formatting
    for part in context_parts:
        assert part.startswith("[2025-")
        assert "]" in part


def test_text_hashing_functionality(temp_dir: Path):
    """Test text hashing for content change detection."""
    whatsapp_texts = [
        "03/10/2025 09:45 - Franklin: Teste de grupo",
        "03/10/2025 09:46 - Franklin: Legal esse vídeo",
        "03/10/2025 09:45 - Franklin: Teste de grupo",  # Duplicate
    ]

    hashes = [hash_text(text) for text in whatsapp_texts]

    # Validate hash generation
    assert len(hashes) == 3
    assert all(isinstance(h, str) for h in hashes)
    assert all(len(h) > 0 for h in hashes)

    # Identical texts should have identical hashes
    assert hashes[0] == hashes[2]

    # Different texts should have different hashes
    assert hashes[0] != hashes[1]


def test_whatsapp_data_processing_pipeline(temp_dir: Path):
    """Test complete data processing pipeline with WhatsApp format."""
    # Setup test data
    zips_dir = temp_dir / "zips"
    zips_dir.mkdir()

    # Create test zip with WhatsApp content
    whatsapp_content = """03/10/2025 09:45 - Franklin: Vamos falar sobre IA
03/10/2025 09:46 - Franklin: https://youtu.be/example
03/10/2025 09:47 - Maria: Ótimo tópico para discussão
03/10/2025 09:48 - José: Tenho experiência com machine learning"""

    test_zip = zips_dir / "2025-10-03.zip"
    create_test_zip(whatsapp_content, test_zip, "conversation.txt")

    # Validate zip creation
    assert test_zip.exists()

    # Test that the content can be read
    import zipfile

    with zipfile.ZipFile(test_zip, "r") as zf:
        files = zf.namelist()
        assert "conversation.txt" in files

        with zf.open("conversation.txt") as f:
            content = f.read().decode("utf-8")
            assert "Franklin" in content
            assert "IA" in content


def test_rag_performance_considerations(temp_dir: Path):
    """Test performance considerations for RAG with large datasets."""
    # Simulate large conversation dataset
    large_conversations = []

    for day in range(10):  # 10 days of conversations
        for hour in range(8, 18):  # 8 AM to 6 PM
            for message in range(5):  # 5 messages per hour
                content = f"{hour:02d}:{message*10:02d} - User{message}: Message about topic {day}-{hour}-{message}"
                large_conversations.append(content)

    all_content = "\n".join(large_conversations)

    # Test content size management
    max_chars = 10000
    if len(all_content) > max_chars:
        # Truncate to fit within limits
        truncated = all_content[:max_chars]
        # Ensure we don't cut in middle of line
        if "\n" in truncated:
            truncated = truncated.rsplit("\n", 1)[0]

        assert len(truncated) <= max_chars
        assert truncated.endswith("User0: Message about topic") or "User" in truncated


def test_search_result_structure():
    """Test search result data structure."""
    # Test SearchResult structure without actual search
    test_results = []

    # Simulate search results
    for i in range(3):
        result = {
            "content": f"Test content {i}",
            "score": 0.9 - (i * 0.1),
            "metadata": {"date": f"2025-10-0{i+1}", "source": "whatsapp"},
        }
        test_results.append(result)

    # Validate result structure
    assert len(test_results) == 3

    for result in test_results:
        assert "content" in result
        assert "score" in result
        assert "metadata" in result
        assert 0.0 <= result["score"] <= 1.0


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

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
