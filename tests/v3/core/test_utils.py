
import pytest
from egregora_v3.core.utils import simple_chunk_text, slugify


@pytest.mark.parametrize(
    "text, max_len, expected",
    [
        ("Hello World", 60, "hello-world"),
        ("Café", 60, "cafe"),
        ("  leading & trailing spaces  ", 60, "leading-trailing-spaces"),
        ("!@#$%^&*()_=+[]{};:'\",.<>/?`~", 60, "untitled"),
        ("---multiple---hyphens---", 60, "multiple-hyphens"),
        ("A" * 100, 20, "aaaaaaaaaaaaaaaaaaaa"),
        ("long text that gets cut off", 10, "long-text"),
        ("empty input", 60, "empty-input"),
        ("", 60, "untitled"),
        ("trailing-", 60, "trailing"),
    ],
)
def test_slugify(text, max_len, expected):
    """Test the V3 slugify function with various inputs."""
    assert slugify(text, max_len=max_len) == expected


def test_simple_chunk_text_empty():
    assert simple_chunk_text("") == []


def test_simple_chunk_text_short():
    text = "This is a short text."
    assert simple_chunk_text(text, max_chars=100) == [text]


def test_simple_chunk_text_long():
    text = "This is a long text that should be split into multiple chunks."
    chunks = simple_chunk_text(text, max_chars=20, overlap=5)
    assert len(chunks) > 1
    assert chunks[0] == "This is a long text"
    assert "text that should be" in chunks[1]


def test_simple_chunk_text_exact_multiple():
    text = "word " * 20
    chunks = simple_chunk_text(text.strip(), max_chars=50, overlap=10)
    assert len(chunks) > 1


def test_simple_chunk_text_with_overlap():
    text = "one two three four five six seven eight nine ten"
    chunks = simple_chunk_text(text, max_chars=20, overlap=10)
    assert len(chunks) == 4
    assert chunks[0] == "one two three four"
    assert chunks[1] == "four five six seven"
    assert chunks[2] == "six seven eight"
    assert chunks[3] == "eight nine ten"
