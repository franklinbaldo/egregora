"""Tests for PII scrubbing utilities."""

from unittest.mock import Mock

from egregora.security.pii import scrub_pii


class TestPIIScrubbing:
    def test_scrub_email(self):
        text = "Contact me at user@example.com for details."
        expected = "Contact me at <EMAIL_REDACTED> for details."
        assert scrub_pii(text) == expected

    def test_scrub_phone(self):
        phones = [
            "123-456-7890",
            "(123) 456-7890",
            "+1 123 456 7890",
            "123.456.7890",
        ]
        for phone in phones:
            text = f"Call {phone} now."
            # Note: Regex might leave leftover whitespace depending on pattern details
            # The current pattern consumes separators.
            result = scrub_pii(text)
            assert "<PHONE_REDACTED>" in result
            assert phone not in result

    def test_scrub_multiple(self):
        text = "Email: test@test.com, Phone: 555-123-4567."
        result = scrub_pii(text)
        assert "<EMAIL_REDACTED>" in result
        assert "<PHONE_REDACTED>" in result

    def test_config_disable_all(self):
        config = Mock()
        config.privacy.pii_detection_enabled = False
        text = "user@example.com"
        assert scrub_pii(text, config) == text

    def test_config_selective(self):
        config = Mock()
        config.privacy.pii_detection_enabled = True
        config.privacy.scrub_emails = False
        config.privacy.scrub_phones = True

        text = "user@example.com 555-123-4567"
        result = scrub_pii(text, config)
        assert "user@example.com" in result
        assert "<PHONE_REDACTED>" in result

    def test_no_pii(self):
        text = "Just some normal text."
        assert scrub_pii(text) == text
