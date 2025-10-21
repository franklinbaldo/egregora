import pytest

from egregora.privacy import PrivacyViolationError, validate_newsletter_privacy


def test_validate_newsletter_privacy_detects_phone_numbers() -> None:
    with pytest.raises(PrivacyViolationError):
        validate_newsletter_privacy("Contato: +55 11 94529-4774")

    with pytest.raises(PrivacyViolationError):
        validate_newsletter_privacy("Mensagem (415) 656-5918 compartilhada")


def test_validate_newsletter_privacy_allows_safe_content() -> None:
    text = "Estamos alinhados com (123e4567-e89b-12d3-a456-426614174000) para 2024."
    assert validate_newsletter_privacy(text) is True


def test_validate_newsletter_privacy_ignores_uuid_segments() -> None:
    anonymized_author = "12345678-1234-1234-1234-123456789abc"
    transcript_line = f"12:00 — {anonymized_author}: Olá, mundo!"

    assert validate_newsletter_privacy(transcript_line) is True


def test_validate_newsletter_privacy_allows_parenthesized_year() -> None:
    assert validate_newsletter_privacy("Relembramos os eventos de (2024).") is True
