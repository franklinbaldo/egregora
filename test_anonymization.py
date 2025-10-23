#!/usr/bin/env python3
"""Quick test for anonymization functionality."""

import polars as pl
from src.egregora.anonymizer import anonymize_author, anonymize_mentions, anonymize_dataframe


def test_anonymize_author():
    """Test deterministic UUID5 author anonymization."""
    author1 = "João Silva"
    author2 = "joão silva"  # Same author, different case
    author3 = "Maria Santos"

    anon1 = anonymize_author(author1)
    anon2 = anonymize_author(author2)
    anon3 = anonymize_author(author3)

    print(f"Original: '{author1}' → Anonymized: '{anon1}'")
    print(f"Original: '{author2}' → Anonymized: '{anon2}'")
    print(f"Original: '{author3}' → Anonymized: '{anon3}'")

    assert anon1 == anon2, "Same author should have same pseudonym"
    assert anon1 != anon3, "Different authors should have different pseudonyms"
    assert len(anon1) == 8, "Pseudonym should be 8 chars"
    print("✓ Author anonymization works\n")


def test_anonymize_mentions():
    """Test WhatsApp mention replacement."""
    text_with_mention = "Hey \u2068João Silva\u2069 how are you?"
    text_without_mention = "Hey everyone, how are you?"

    anon1 = anonymize_mentions(text_with_mention)
    anon2 = anonymize_mentions(text_without_mention)

    print(f"Original: '{text_with_mention}'")
    print(f"Anonymized: '{anon1}'")
    print(f"No mentions: '{anon2}'\n")

    assert "\u2068" not in anon1, "Unicode markers should be removed"
    assert "João Silva" not in anon1, "Real name should be anonymized"
    assert anon2 == text_without_mention, "Text without mentions unchanged"
    print("✓ Mention anonymization works\n")


def test_anonymize_dataframe():
    """Test DataFrame anonymization."""
    df = pl.DataFrame({
        "timestamp": ["2025-01-01 10:00:00", "2025-01-01 10:05:00"],
        "author": ["João Silva", "Maria Santos"],
        "message": [
            "Hello \u2068Maria Santos\u2069!",
            "Hi \u2068João Silva\u2069, how are you?"
        ]
    })

    print("Original DataFrame:")
    print(df)
    print()

    anonymized = anonymize_dataframe(df)

    print("Anonymized DataFrame:")
    print(anonymized)
    print()

    assert "João Silva" not in str(anonymized["author"].to_list())
    assert "Maria Santos" not in str(anonymized["author"].to_list())
    assert "\u2068" not in str(anonymized["message"].to_list())
    print("✓ DataFrame anonymization works\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Anonymization")
    print("=" * 60 + "\n")

    test_anonymize_author()
    test_anonymize_mentions()
    test_anonymize_dataframe()

    print("=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
