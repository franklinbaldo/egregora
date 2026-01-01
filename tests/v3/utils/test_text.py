
import pytest
from egregora_v3.utils.text import simple_chunk_text, slugify


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
    expected_chunks = [
        "one two three four",
        "four five six seven",
        "six seven eight",
        "eight nine ten",
    ]
    assert chunks == expected_chunks


def test_slugify():
    assert slugify("Hello World") == "hello-world"
    assert slugify("Café") == "cafe"
    assert slugify("A" * 100, max_len=20) == "aaaaaaaaaaaaaaaaaaaa"
    assert slugify("!@#$%^&*()") == "untitled"
    assert slugify(" leading-and-trailing- ") == "leading-and-trailing"
