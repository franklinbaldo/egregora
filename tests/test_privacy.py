from __future__ import annotations

import sys
from pathlib import Path
from datetime import date
from types import SimpleNamespace
import pytest
import os
import shutil
import zipfile
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.anonymizer import Anonymizer
from egregora.config import PipelineConfig
from egregora.llm_models import SystemMessageLabel
from egregora.pipeline import _prepare_transcripts
from egregora.privacy import PrivacyViolationError, validate_newsletter_privacy
from egregora.generator import PostGenerator
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


# From test_privacy_e2e.py
def test_prepare_transcripts_anonymizes_authors(temp_dir) -> None:
    config = PipelineConfig.with_defaults(
        zips_dir=temp_dir,
        posts_dir=temp_dir,
    )

    class RecordingClassifier:
        def __init__(self) -> None:
            self.captured: list[str] = []

        def filter_transcript(self, text: str) -> tuple[str, list[SystemMessageLabel]]:
            self.captured.append(text)
            cleaned_lines = [
                line
                for line in text.splitlines()
                if "mudou o assunto" not in line.casefold()
                and "media omitted" not in line.casefold()
                and "<mídia oculta>" not in line.casefold()
            ]
            cleaned = "\n".join(cleaned_lines)
            return cleaned, [SystemMessageLabel() for _ in cleaned_lines]

    classifier = RecordingClassifier()

    transcripts = [
        (
            date(2024, 1, 1),
            "\n".join(
                [
                    "12:00 - João Silva: Fala com Maria no WhatsApp do Pedro 11 91234-5678",
                    "12:15 - João Silva: Mudou o assunto do grupo para Reunião",
                    "13:00 - +55 21 99876-5432: Meu número é 21 99876-5432",
                    "13:30 - João Silva: <mídia oculta>",
                ]
            ),
        )
    ]

    sanitized = _prepare_transcripts(transcripts, config, classifier=classifier)
    sanitized_text = sanitized[0][1]

    assert "João Silva" not in sanitized_text
    assert sanitized_text.count("Member-") >= 1
    assert "Maria" in sanitized_text  # conteúdo das mensagens permanece intacto
    assert "Mudou o assunto" not in sanitized_text
    assert "<mídia oculta>" not in sanitized_text
    assert classifier.captured, "classifier should receive anonymized text"
    assert all("Member-" in captured for captured in classifier.captured)


def test_prepare_transcripts_noop_when_disabled(temp_dir) -> None:
    config = PipelineConfig.with_defaults(
        zips_dir=temp_dir,
        posts_dir=temp_dir,
    )
    config.anonymization.enabled = False

    original_text = "12:00 - João Silva: Mensagem com telefone 11 91234-5678"
    transcripts = [(date(2024, 1, 1), original_text)]

    sanitized = _prepare_transcripts(transcripts, config)

    assert sanitized[0][1] == original_text


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


def test_system_instruction_includes_privacy_rules(monkeypatch):
    _install_generator_stubs(monkeypatch)
    config = PipelineConfig.with_defaults()
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


# From test_unified_processor_anonymization.py
HAS_GEMINI_KEY = bool(os.getenv("GEMINI_API_KEY"))


@pytest.mark.skip(reason="Group discovery is temporarily disabled")
@pytest.mark.skipif(
    not HAS_GEMINI_KEY,
    reason="GEMINI_API_KEY not configured; skipping live anonymization integration test.",
)
def test_unified_processor_anonymizes_transcripts(tmp_path: Path) -> None:
    base_dir = Path("tests/temp_output/anonymization")
    shutil.rmtree(base_dir, ignore_errors=True)

    zips_dir = base_dir / "zips"
    posts_dir = base_dir / "posts"
    zips_dir.mkdir(parents=True, exist_ok=True)
    posts_dir.mkdir(parents=True, exist_ok=True)

    zip_path = zips_dir / "Conversa do WhatsApp com Teste.zip"
    chat_txt_path = tmp_path / "_chat.txt"
    with open(chat_txt_path, "w", encoding="utf-8") as handle:
        handle.write("03/10/2025 09:45 - +55 11 94529-4774: Teste de grupo\n")

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(chat_txt_path, arcname="_chat.txt")

    config = PipelineConfig.with_defaults(
        zips_dir=zips_dir,
        posts_dir=posts_dir,
        model="gemini/gemini-1.5-flash-latest",
        timezone=ZoneInfo("America/Sao_Paulo"),
    )

    processor = UnifiedProcessor(config)

    try:
        results = processor.process_all(days=1)
    finally:
        chat_txt_path.unlink(missing_ok=True)

    slug, generated_posts = next(iter(results.items()))
    output_file = generated_posts[0]
    assert output_file.exists()

    content = output_file.read_text(encoding="utf-8")
    if "+55 11 94529-4774" in content:
        raise PrivacyViolationError("Telefone não deveria aparecer no post gerado")
    assert "Member-" in content or "Membro" in content

    shutil.rmtree(base_dir, ignore_errors=True)


@pytest.mark.skip(reason="Group discovery is temporarily disabled")
def test_unified_processor_anonymizes_transcripts_no_gemini(tmp_path: Path) -> None:
    base_dir = Path("tests/temp_output/anonymization")
    shutil.rmtree(base_dir, ignore_errors=True)

    zips_dir = base_dir / "zips"
    posts_dir = base_dir / "posts"
    zips_dir.mkdir(parents=True, exist_ok=True)
    posts_dir.mkdir(parents=True, exist_ok=True)

    zip_path = zips_dir / "Conversa do WhatsApp com Teste.zip"
    chat_txt_path = tmp_path / "_chat.txt"
    with open(chat_txt_path, "w", encoding="utf-8") as handle:
        handle.write("03/10/2025 09:45 - +55 11 94529-4774: Teste de grupo\n")

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(chat_txt_path, arcname="_chat.txt")

    config = PipelineConfig.with_defaults(
        zips_dir=zips_dir,
        posts_dir=posts_dir,
        model="none",  # Disable Gemini for this test
        timezone=ZoneInfo("America/Sao_Paulo"),
    )

    processor = UnifiedProcessor(config)

    try:
        results = processor.process_all(days=1)
    finally:
        chat_txt_path.unlink(missing_ok=True)

    slug, generated_posts = next(iter(results.items()))
    output_file = generated_posts[0]
    assert output_file.exists()

    content = output_file.read_text(encoding="utf-8")
    if "+55 11 94529-4774" in content:
        raise PrivacyViolationError("Telefone não deveria aparecer no post gerado")
    assert "Member-" in content or "Membro" in content

    shutil.rmtree(base_dir, ignore_errors=True)
