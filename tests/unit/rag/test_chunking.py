import pytest
from egregora.rag.chunking import simple_chunk_text, DEFAULT_MAX_CHARS, DEFAULT_CHUNK_OVERLAP

class TestSimpleChunkText:
    def test_empty_text(self):
        assert simple_chunk_text("") == []

    def test_short_text(self):
        text = "This is a short text."
        chunks = simple_chunk_text(text, max_chars=100)
        assert chunks == [text]

    def test_exact_length_text(self):
        text = "abcde"
        chunks = simple_chunk_text(text, max_chars=5)
        assert chunks == [text]

    def test_split_text(self):
        # "word1 word2 word3" -> 17 chars
        text = "word1 word2 word3 word4 word5"
        # max_chars=12.
        # "word1 word2" = 11 chars. + " " + "word3" = 17.
        # Should split after word2.

        chunks = simple_chunk_text(text, max_chars=12, overlap=0)
        # 1: "word1 word2"
        # 2: "word3 word4"
        # 3: "word5"

        assert len(chunks) >= 3
        assert chunks[0] == "word1 word2"
        assert chunks[1] == "word3 word4"
        assert chunks[2] == "word5"

    def test_overlap(self):
        text = "word1 word2 word3 word4"
        # max=12 (holds 2 words)
        # overlap=6 (holds 1 word + space)

        chunks = simple_chunk_text(text, max_chars=12, overlap=6)
        # 1: "word1 word2" (11 chars)
        # Overlap from end: "word2" (5 chars).
        # Next starts with "word2".
        # 2: "word2 word3" (11 chars)
        # Overlap: "word3"
        # 3: "word3 word4"

        assert chunks[0] == "word1 word2"
        assert chunks[1] == "word2 word3"
        assert chunks[2] == "word3 word4"

    def test_long_single_word(self):
        # Function implementation splits by space, so long word stays as one item in 'words' list.
        # It should be returned as is, potentially exceeding max_chars.

        long_word = "a" * 20
        chunks = simple_chunk_text(long_word, max_chars=10)
        assert len(chunks) == 1
        assert chunks[0] == long_word
