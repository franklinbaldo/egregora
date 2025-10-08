from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.config import PipelineConfig
from egregora.llm_models import SystemMessageLabel
from egregora.pipeline import _prepare_transcripts


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
