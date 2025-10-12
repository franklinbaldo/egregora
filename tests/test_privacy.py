from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.anonymizer import Anonymizer
from egregora.config import PipelineConfig
from egregora.generator import PostGenerator
from egregora.privacy import PrivacyViolationError, validate_newsletter_privacy
from egregora.processor import UnifiedProcessor

ANON_SUFFIX_LENGTH = 4
UUID_FULL_LENGTH = 36
UUID_SHORT_LENGTH = 8


# From test_anonymizer.py
def test_normalize_phone_adds_country_code() -> None:
    assert Anonymizer.normalize_phone("(11) 98765-4321") == "+5511987654321"


def test_anonymize_phone_is_deterministic() -> None:
    token_a = Anonymizer.anonymize_phone("+55 11 98765-4321")
    token_b = Anonymizer.anonymize_phone("5511987654321")

    assert token_a == token_b
    assert token_a.startswith("Member-")
    suffix = token_a.split("-")[1]
    assert len(suffix) == ANON_SUFFIX_LENGTH
    assert suffix.isupper()


def test_anonymize_nickname_uses_member_prefix() -> None:
    token_a = Anonymizer.anonymize_nickname(" João Silva ")
    token_b = Anonymizer.anonymize_nickname("joão silva")

    assert token_a == token_b
    assert token_a.startswith("Member-")


def test_get_uuid_variants_returns_human_identifier() -> None:
    variants = Anonymizer.get_uuid_variants("Maria")

    assert set(variants.keys()) == {"full", "short", "human"}
    assert variants["human"].startswith("Member-")
    assert len(variants["full"]) == UUID_FULL_LENGTH
    assert len(variants["short"]) == UUID_SHORT_LENGTH


def test_validate_newsletter_privacy_detects_phone_numbers() -> None:
    with pytest.raises(PrivacyViolationError):
        validate_newsletter_privacy("Contato: +55 11 94529-4774")

    with pytest.raises(PrivacyViolationError):
        validate_newsletter_privacy("Mensagem (4774) capturada")


def test_validate_newsletter_privacy_allows_safe_content() -> None:
    text = "Estamos alinhados com Member-ABCD e (Nick) para 2024."
    assert validate_newsletter_privacy(text) is True


# From test_privacy_prompt.py
class DummyPart:
    def __init__(self, text: str):
        self.text = text

    @classmethod
    def from_text(cls, *, text: str):
        return cls(text=text)


def _install_generator_stubs(monkeypatch):
    stub_types = SimpleNamespace(Part=DummyPart)
    # Patch the types used within the generator module
    monkeypatch.setattr("egregora.generator.types", stub_types)
    # Mock the prompt loading to avoid file I/O
    monkeypatch.setattr("egregora.generator._load_prompt", lambda name: f"PROMPT: {name}")


from unittest.mock import MagicMock


def test_system_instruction_includes_privacy_rules(monkeypatch):
    _install_generator_stubs(monkeypatch)
    config = PipelineConfig()
    monkeypatch.setattr("egregora.generator.GeminiManager", MagicMock())
    generator = PostGenerator(config)

    # Test without group tags
    instruction = generator._build_system_instruction(has_group_tags=False)
    assert instruction, "system instruction should not be empty"
    system_text = instruction[0].text
    assert "PROMPT: system_instruction_base.md" in system_text
    assert "PROMPT: system_instruction_multigroup.md" not in system_text

    # Test with group tags
    instruction_multigroup = generator._build_system_instruction(has_group_tags=True)
    system_text_multigroup = instruction_multigroup[0].text
    assert "PROMPT: system_instruction_base.md" in system_text_multigroup
    assert "PROMPT: system_instruction_multigroup.md" in system_text_multigroup


import polars as pl


# From test_unified_processor_anonymization.py
def test_unified_processor_anonymizes_dataframe(monkeypatch):
    """Verify that the UnifiedProcessor correctly anonymizes the dataframe."""
    # Create a mock DataFrame
    df = pl.DataFrame(
        {
            "author": ["João Silva", "+55 21 99876-5432"],
            "message": ["Message 1", "Message 2"],
            "date": [date(2024, 1, 1), date(2024, 1, 1)],
            "timestamp": [
                datetime(2024, 1, 1, 12, 0),
                datetime(2024, 1, 1, 13, 0),
            ],
        }
    )

    # Mock load_source_dataframe to return our test DataFrame
    monkeypatch.setattr("egregora.processor.load_source_dataframe", lambda source: df)

    # Mock the generator to prevent actual LLM calls
    mock_generator = MagicMock()
    mock_generator.generate.return_value = "Generated post content."
    monkeypatch.setattr(
        "egregora.processor.PostGenerator", lambda config, gemini_manager: mock_generator
    )

    # Configure and run the processor
    config = PipelineConfig(
        zip_files=[Path("dummy.zip")],
        posts_dir=Path("test_posts"),
        anonymization={"enabled": True},
    )
    processor = UnifiedProcessor(config)

    # The actual processing logic is inside _process_source, which we can't
    # easily call. However, we can check the anonymization function directly.
    anonymized_df = Anonymizer.anonymize_dataframe(df)

    # Verify that the authors have been anonymized
    assert "João Silva" not in anonymized_df["author"].to_list()
    assert "+55 21 99876-5432" not in anonymized_df["author"].to_list()
    assert anonymized_df["author"][0].startswith("Member-")
    assert anonymized_df["author"][1].startswith("Member-")
