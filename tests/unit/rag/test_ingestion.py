"""Unit tests for RAG ingestion and chunking (V2 and V3)."""

# V2 imports and tests
from egregora.rag.ingestion import _simple_chunk_text
from egregora_v3.infra.rag import simple_chunk_text as simple_chunk_text_v3

# --- V2 Tests ---


def test_v2_simple_chunk_text_empty():
    """Empty text should produce a single empty chunk in V2."""
    # V2 returns [''] for empty input, unlike V3 which returns []
    assert _simple_chunk_text("") == [""]


def test_v2_simple_chunk_text_short():
    """Text shorter than max_chars should produce a single chunk."""
    text = "This is a short text."
    assert _simple_chunk_text(text, max_chars=100) == [text]


def test_v2_simple_chunk_text_long():
    """Long text should be split into multiple chunks."""
    text = "This is a long text that should be split into multiple chunks."
    chunks = _simple_chunk_text(text, max_chars=30, overlap=10)
    assert len(chunks) > 1
    assert chunks[0] == "This is a long text that"
    assert "text that should be split" in chunks[1]


def test_v2_simple_chunk_text_exact_multiple():
    """Text that is an exact multiple of chunk size should be split correctly."""
    text = "word " * 20  # 100 chars
    chunks = _simple_chunk_text(text.strip(), max_chars=50, overlap=10)
    assert len(chunks) == 3


def test_v2_simple_chunk_text_with_overlap():
    """Chunks should have the specified overlap."""
    text = "one two three four five six seven eight nine ten"
    chunks = _simple_chunk_text(text, max_chars=20, overlap=10)
    assert len(chunks) == 4
    assert chunks[0] == "one two three four"
    assert chunks[1] == "four five six seven"
    assert chunks[2] == "six seven eight"
    assert chunks[3] == "eight nine ten"


# --- V3 Tests ---


def test_v3_simple_chunk_text_empty():
    assert simple_chunk_text_v3("") == []


def test_v3_simple_chunk_text_short():
    text = "This is a short text."
    assert simple_chunk_text_v3(text, max_chars=100) == [text]


def test_v3_simple_chunk_text_long():
    text = "This is a long text that should be split into multiple chunks."
    chunks = simple_chunk_text_v3(text, max_chars=20, overlap=5)
    assert len(chunks) > 1
    assert chunks[0] == "This is a long text"
    assert "text that should be" in chunks[1]


def test_v3_simple_chunk_text_exact_multiple():
    text = "word " * 20
    chunks = simple_chunk_text_v3(text.strip(), max_chars=50, overlap=10)
    assert len(chunks) > 1


def test_v3_simple_chunk_text_with_overlap():
    text = "one two three four five six seven eight nine ten"
    chunks = simple_chunk_text_v3(text, max_chars=20, overlap=10)
    assert len(chunks) == 4
    assert chunks[0] == "one two three four"
    assert chunks[1] == "four five six seven"
    assert chunks[2] == "six seven eight"
    assert chunks[3] == "eight nine ten"
