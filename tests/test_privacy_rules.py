import pytest

from egregora.privacy import PrivacyViolationError, validate_newsletter_privacy


def test_validate_newsletter_privacy_detects_phone_numbers() -> None:
    with pytest.raises(PrivacyViolationError):
        validate_newsletter_privacy("Contato: +55 11 94529-4774")

    with pytest.raises(PrivacyViolationError):
        validate_newsletter_privacy("Mensagem (4774) capturada")


def test_validate_newsletter_privacy_allows_safe_content() -> None:
    text = "Estamos alinhados com (123e4567-e89b-12d3-a456-426614174000) para 2024."
    assert validate_newsletter_privacy(text) is True
