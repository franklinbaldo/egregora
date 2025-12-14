"""Tests for privacy utilities."""

import pytest
import uuid
from egregora.privacy import scrub_pii, anonymize_author

def test_scrub_pii_email():
    text = "Contact me at test@example.com"
    result = scrub_pii(text)
    assert result == "Contact me at <EMAIL_REDACTED>"

def test_scrub_pii_phone():
    text = "Call me at 123-456-7890"
    result = scrub_pii(text)
    assert result == "Call me at <PHONE_REDACTED>"

def test_anonymize_author_consistency():
    namespace = uuid.uuid4()
    author = "John Doe"
    uuid1 = anonymize_author(author, namespace)
    uuid2 = anonymize_author(author, namespace)
    assert uuid1 == uuid2
    assert uuid1 != author

def test_anonymize_author_different_authors():
    namespace = uuid.uuid4()
    uuid1 = anonymize_author("John Doe", namespace)
    uuid2 = anonymize_author("Jane Doe", namespace)
    assert uuid1 != uuid2

def test_scrub_pii_with_config_disabled():
    # Mock config object
    class MockPrivacy:
        pii_detection_enabled = False
        scrub_emails = True
        scrub_phones = True
    class MockConfig:
        privacy = MockPrivacy()

    text = "test@example.com"
    # We pass MockConfig which mocks EgregoraConfig structure
    assert scrub_pii(text, MockConfig()) == text

def test_scrub_pii_with_config_granular():
    class MockPrivacy:
        pii_detection_enabled = True
        scrub_emails = True
        scrub_phones = False
    class MockConfig:
        privacy = MockPrivacy()

    text = "test@example.com 123-456-7890"
    result = scrub_pii(text, MockConfig())
    assert "<EMAIL_REDACTED>" in result
    assert "123-456-7890" in result
