
import pytest
from egregora_v3.core.text_utils import slugify, simple_chunk_text


def test_slugify_simple():
    assert slugify("Hello World") == "hello-world"


def test_slugify_unicode():
    assert slugify("Café") == "cafe"


def test_slugify_long_text():
    long_text = "a" * 100
    assert slugify(long_text, max_len=20) == "aaaaaaaaaaaaaaaaaaaa"


def test_slugify_with_special_chars():
    assert slugify("!@#$%^&*()_+=") == "untitled"


def test_slugify_with_leading_trailing_hyphens():
    assert slugify("---hello-world---") == "hello-world"


def test_slugify_with_consecutive_hyphens():
    assert slugify("hello--world") == "hello-world"


def test_slugify_empty_string():
    assert slugify("") == "untitled"


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
