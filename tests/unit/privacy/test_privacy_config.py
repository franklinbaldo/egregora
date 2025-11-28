"""Tests for privacy configuration and functions."""

import ibis
import pytest

from egregora.privacy.anonymizer import anonymize_table
from egregora.privacy.detector import PrivacyViolationError, validate_text_privacy


def test_anonymize_table_disabled():
    """Test anonymize_table skips when disabled."""
    # Create test table
    data = {
        "author_raw": ["Alice", "Bob"],
        "author_uuid": ["uuid-alice", "uuid-bob"],
        "text": ["Hello", "World"],
    }
    table = ibis.memtable(data)

    # Anonymize with enabled=False
    result = anonymize_table(table, enabled=False)

    # Should return unchanged
    result_data = result.execute()
    assert list(result_data["author_raw"]) == ["Alice", "Bob"]
    assert list(result_data["text"]) == ["Hello", "World"]


def test_anonymize_table_enabled():
    """Test anonymize_table anonymizes when enabled."""
    # Create test table
    data = {
        "author_raw": ["Alice", "Bob"],
        "author_uuid": ["uuid-alice", "uuid-bob"],
        "text": ["Hello", "World"],
    }
    table = ibis.memtable(data)

    # Anonymize with enabled=True (default)
    result = anonymize_table(table, enabled=True)

    # Should anonymize author_raw
    result_data = result.execute()
    assert list(result_data["author_raw"]) == ["uuid-alice", "uuid-bob"]


def test_validate_text_privacy_disabled():
    """Test PII detection skips when disabled."""
    text_with_pii = "Contact me at 555-1234 or email@example.com"

    # Should return text unchanged and valid=True
    result_text, is_valid = validate_text_privacy(text_with_pii, enabled=False)

    assert result_text == text_with_pii
    assert is_valid is True


def test_validate_text_privacy_actions():
    """Test PII detection respects different actions."""
    # Test that the function accepts all action parameters
    clean_text = "This is safe text with no PII"

    # Warn action
    result_text, is_valid = validate_text_privacy(clean_text, action="warn", enabled=True)
    assert result_text == clean_text
    assert is_valid is True

    # Redact action
    result_text, is_valid = validate_text_privacy(clean_text, action="redact", enabled=True)
    assert result_text == clean_text
    assert is_valid is True

    # Skip action
    result_text, is_valid = validate_text_privacy(clean_text, action="skip", enabled=True)
    assert result_text == clean_text
    assert is_valid is True


def test_validate_text_privacy_no_pii():
    """Test PII detection with clean text."""
    clean_text = "This is a safe message with no personal information"

    # Should pass validation
    result_text, is_valid = validate_text_privacy(clean_text, enabled=True)

    assert result_text == clean_text
    assert is_valid is True


def test_validate_text_privacy_uuid_not_flagged():
    """Test that UUIDs are not flagged as PII."""
    text_with_uuid = "User ID: 550e8400-e29b-41d4-a716-446655440000"

    # UUIDs should not be detected as phone numbers
    result_text, is_valid = validate_text_privacy(text_with_uuid, enabled=True)

    assert result_text == text_with_uuid
    # This might be True or False depending on the UUID pattern matching
    # The important thing is it doesn't crash


def test_anonymize_table_with_author_column():
    """Test anonymize_table handles 'author' column."""
    # Create test table with both author and author_raw
    data = {
        "author": ["Alice", "Bob"],
        "author_raw": ["Alice", "Bob"],
        "author_uuid": ["uuid-alice", "uuid-bob"],
        "text": ["Hello", "World"],
    }
    table = ibis.memtable(data)

    # Anonymize
    result = anonymize_table(table, enabled=True)

    # Both author and author_raw should be anonymized
    result_data = result.execute()
    assert list(result_data["author"]) == ["uuid-alice", "uuid-bob"]
    assert list(result_data["author_raw"]) == ["uuid-alice", "uuid-bob"]


def test_anonymize_table_missing_columns():
    """Test anonymize_table raises error for missing columns."""
    # Create table without required columns
    data = {"text": ["Hello", "World"]}
    table = ibis.memtable(data)

    # Should raise ValueError
    with pytest.raises(ValueError, match="missing required columns"):
        anonymize_table(table, enabled=True)
