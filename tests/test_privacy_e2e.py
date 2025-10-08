from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.config import PipelineConfig
from test_framework.helpers import run_pipeline_for_test


def test_prepare_transcripts_anonymizes_authors(temp_dir) -> None:
    config = PipelineConfig.with_defaults(
        zips_dir=temp_dir,
        newsletters_dir=temp_dir,
    )

    transcripts = [
        (
            date(2024, 1, 1),
            "\n".join(
                [
                    "12:00 - João Silva: Fala com Maria no WhatsApp do Pedro 11 91234-5678",
                    "13:00 - +55 21 99876-5432: Meu número é 21 99876-5432",
                ]
            ),
        )
    ]

    sanitized = run_pipeline_for_test(transcripts, config, temp_dir)
    sanitized_text = sanitized[0][1]

    assert "João Silva" not in sanitized_text
    assert sanitized_text.count("Member-") >= 1
    assert "Maria" in sanitized_text  # conteúdo das mensagens permanece intacto


def test_prepare_transcripts_noop_when_disabled(temp_dir) -> None:
    config = PipelineConfig.with_defaults(
        zips_dir=temp_dir,
        newsletters_dir=temp_dir,
    )
    config.anonymization.enabled = False

    original_text = "12:00 - João Silva: Mensagem com telefone 11 91234-5678"
    transcripts = [(date(2024, 1, 1), original_text)]

    sanitized = run_pipeline_for_test(transcripts, config, temp_dir)
    sanitized_text = sanitized[0][1]

    assert sanitized_text == original_text
    assert "João Silva" in sanitized_text
    assert "Member-" not in sanitized_text