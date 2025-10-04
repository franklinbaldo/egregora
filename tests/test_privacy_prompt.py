from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import egregora.pipeline as pipeline


class DummyPart:
    def __init__(self, text: str):
        self.text = text

    @classmethod
    def from_text(cls, *, text: str):
        return cls(text=text)


class DummyContent:
    def __init__(self, *, role: str, parts: list[DummyPart]):
        self.role = role
        self.parts = parts


class DummyGenerateContentConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def _install_pipeline_stubs(monkeypatch):
    stub_types = SimpleNamespace(
        Part=DummyPart,
        Content=DummyContent,
        GenerateContentConfig=DummyGenerateContentConfig,
    )
    monkeypatch.setattr(pipeline, "types", stub_types)
    monkeypatch.setattr(pipeline, "genai", object())


class DummyChunk:
    def __init__(self, text: str):
        self.text = text


class DummyModelAPI:
    def __init__(self, responses: list[str]):
        self._responses = responses

    def generate_content_stream(self, *, model: str, contents, config):  # noqa: ANN001
        for text in self._responses:
            yield DummyChunk(text)


class DummyClient:
    def __init__(self, responses: list[str]):
        self.models = DummyModelAPI(responses)


def test_system_instruction_includes_privacy_rules(monkeypatch):
    _install_pipeline_stubs(monkeypatch)

    instruction = pipeline.build_system_instruction()
    assert instruction, "system instruction should not be empty"

    system_text = instruction[0].text
    assert "PRIVACIDADE — INSTRUÇÕES CRÍTICAS" in system_text
    assert "Nunca repita nomes próprios" in system_text
    assert "identificadores anônimos" in system_text


def test_prepare_transcripts_anonymizes_authors(monkeypatch):
    _install_pipeline_stubs(monkeypatch)

    config = pipeline.PipelineConfig.with_defaults()
    transcripts = [
        (date(2024, 1, 1), "12:00 - João: Mensagem importante.\n"),
        (date(2024, 1, 2), "[08:45:10] +551199887766 - Maria: Outra mensagem."),
    ]

    sanitized = pipeline._prepare_transcripts(transcripts, config)

    sanitized_text = "\n".join(text for _, text in sanitized)
    assert "João" not in sanitized_text
    assert "Maria" not in sanitized_text
    assert "Member-" in sanitized_text
    assert "User-" in sanitized_text
