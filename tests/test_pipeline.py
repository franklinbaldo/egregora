"""Tests for the post pipeline helpers."""

from __future__ import annotations

from datetime import date, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.pipeline import build_llm_input, _anonymize_transcript_line


def _build_transcript(day: int) -> tuple[date, str]:
    return date(2025, 1, day), f"Mensagem do dia {day}."


def test_build_llm_input_uses_singular_label_for_one_day() -> None:
    prompt = build_llm_input(
        group_name="Grupo Teste",
        timezone=timezone.utc,
        transcripts=[_build_transcript(1)],
        previous_post=None,
    )

    assert "TRANSCRITO BRUTO DO ÚLTIMO DIA" in prompt


def test_build_llm_input_uses_plural_label_for_multiple_days() -> None:
    prompt = build_llm_input(
        group_name="Grupo Teste",
        timezone=timezone.utc,
        transcripts=[
            _build_transcript(1),
            _build_transcript(2),
            _build_transcript(3),
        ],
        previous_post=None,
    )

    assert "TRANSCRITO BRUTO DOS ÚLTIMOS 3 DIAS" in prompt


def test_anonymize_transcript_line_preserves_leading_bracket() -> None:
    result = _anonymize_transcript_line(
        "[12:34:56] Nome: mensagem",
        anonymize=True,
    )

    assert result.startswith("[12:34:56] ")
