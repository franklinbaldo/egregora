"""Tests for parser performance improvements."""

from datetime import time

import pytest

from egregora.config.settings import PrivacySettings
from egregora.input_adapters.whatsapp.parsing import _parse_message_time, scrub_pii


@pytest.fixture
def mock_config_pii_enabled():
    """Mock EgregoraConfig with PII detection fully enabled."""

    # We only need the privacy part for this test.
    # Using a mock/dummy object avoids a full config dependency.
    class MockConfig:
        privacy = PrivacySettings(pii_detection_enabled=True, scrub_emails=True, scrub_phones=True)

    return MockConfig()


def test_scrub_pii_correctness(mock_config_pii_enabled):
    """Verify scrub_pii correctly redacts both emails and phone numbers."""
    text = "Contact me at test@example.com or on my number (123) 456-7890. Another one is 123.456.7890."
    expected = (
        "Contact me at <EMAIL_REDACTED> or on my number <PHONE_REDACTED>. Another one is <PHONE_REDACTED>."
    )
    assert scrub_pii(text, mock_config_pii_enabled) == expected


def test_scrub_pii_performance(benchmark, mock_config_pii_enabled):
    """Benchmark the performance of the scrub_pii function with more realistic data."""
    # A larger block of text with sparsely distributed PII to better simulate a real chat log.
    lorem_ipsum = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
        * 20
    )
    text = f"Start of text. {lorem_ipsum} Contact me at test@example.com. {lorem_ipsum} Or call (123) 456-7890. {lorem_ipsum} End of text."
    benchmark(scrub_pii, text, mock_config_pii_enabled)


@pytest.fixture
def mock_config_pii_disabled():
    """Mock EgregoraConfig with PII detection disabled."""

    class MockConfig:
        privacy = PrivacySettings(pii_detection_enabled=False, scrub_emails=True, scrub_phones=True)

    return MockConfig()


@pytest.fixture
def mock_config_email_only():
    """Mock EgregoraConfig with email scrubbing only."""

    class MockConfig:
        privacy = PrivacySettings(pii_detection_enabled=True, scrub_emails=True, scrub_phones=False)

    return MockConfig()


@pytest.fixture
def mock_config_phone_only():
    """Mock EgregoraConfig with phone scrubbing only."""

    class MockConfig:
        privacy = PrivacySettings(pii_detection_enabled=True, scrub_emails=False, scrub_phones=True)

    return MockConfig()


@pytest.fixture
def mock_config_pii_enabled_no_scrub():
    """Mock config with PII detection on, but no scrub types selected."""

    class MockConfig:
        privacy = PrivacySettings(pii_detection_enabled=True, scrub_emails=False, scrub_phones=False)

    return MockConfig()


def test_scrub_pii_disabled(mock_config_pii_disabled):
    """Verify scrub_pii returns original text when PII detection is disabled."""
    text = "Contact me at test@example.com or on my number (123) 456-7890."
    assert scrub_pii(text, mock_config_pii_disabled) == text


def test_scrub_pii_email_only(mock_config_email_only):
    """Verify scrub_pii correctly redacts only emails."""
    text = "Contact me at test@example.com or on my number (123) 456-7890."
    expected = "Contact me at <EMAIL_REDACTED> or on my number (123) 456-7890."
    assert scrub_pii(text, mock_config_email_only) == expected


def test_scrub_pii_phone_only(mock_config_phone_only):
    """Verify scrub_pii correctly redacts only phone numbers."""
    text = "Contact me at test@example.com or on my number (123) 456-7890."
    expected = "Contact me at test@example.com or on my number <PHONE_REDACTED>."
    assert scrub_pii(text, mock_config_phone_only) == expected


def test_scrub_pii_enabled_but_no_scrub_types(mock_config_pii_enabled_no_scrub):
    """Verify scrub_pii returns original text when enabled but no types are selected."""
    text = "Contact me at test@example.com or on my number (123) 456-7890."
    assert scrub_pii(text, mock_config_pii_enabled_no_scrub) == text


def test_scrub_pii_no_config():
    """Verify scrub_pii scrubs both email and phone when no config is provided."""
    text = "Contact me at test@example.com or on my number (123) 456-7890."
    expected = "Contact me at <EMAIL_REDACTED> or on my number <PHONE_REDACTED>."
    assert scrub_pii(text, None) == expected


def test_parse_message_time_common_formats():
    """Verify common formats are parsed correctly."""
    assert _parse_message_time("12:30") == time(12, 30)
    assert _parse_message_time("01:15") == time(1, 15)
    assert _parse_message_time("23:59") == time(23, 59)


def test_parse_message_time_ampm():
    """Verify AM/PM parsing."""
    assert _parse_message_time("10:30 PM") == time(22, 30)
    assert _parse_message_time("10:30 pm") == time(22, 30)
    assert _parse_message_time("10:30PM") == time(22, 30)

    assert _parse_message_time("1:30 AM") == time(1, 30)
    assert _parse_message_time("12:00 AM") == time(0, 0)
    assert _parse_message_time("12:30 AM") == time(0, 30)
    assert _parse_message_time("12:00 PM") == time(12, 0)
    assert _parse_message_time("12:30 PM") == time(12, 30)


def test_parse_message_time_variations():
    """Verify variations in whitespace and formatting."""
    assert _parse_message_time("  12:30  ") == time(12, 30)
    assert _parse_message_time("9:05") == time(9, 5)


def test_parse_message_time_invalid():
    """Verify invalid inputs return None."""
    assert _parse_message_time("") is None
    assert _parse_message_time("invalid") is None
    assert _parse_message_time("12:60") is None  # Invalid minute
    assert _parse_message_time("25:00") is None  # Invalid hour
    assert _parse_message_time("10:30 XM") is None  # Invalid suffix
