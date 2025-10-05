from __future__ import annotations

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
    mock_genai = SimpleNamespace(
        Part=DummyPart,
        Content=DummyContent,
    )
    monkeypatch.setattr(pipeline, "genai", mock_genai)
    monkeypatch.setattr(pipeline, "GenerationConfig", DummyGenerateContentConfig)


class DummyChunk:
    def __init__(self, text: str):
        self.text = text


class DummyModel:
    def __init__(self, responses: list[str]):
        self._responses = responses

    def generate_content(self, *, contents, generation_config, system_instruction, stream: bool):
        if not stream:
            raise NotImplementedError("This dummy client only supports streaming.")
        for text in self._responses:
            yield DummyChunk(text)


def test_system_instruction_includes_privacy_rules(monkeypatch):
    _install_pipeline_stubs(monkeypatch)

    instruction = pipeline.build_system_instruction()
    assert instruction, "system instruction should not be empty"

    system_text = instruction
    assert "PRIVACIDADE — INSTRUÇÕES CRÍTICAS" in system_text
    assert "Nunca repita nomes próprios" in system_text
    assert "identificadores anônimos" in system_text


def test_privacy_review_removes_names(monkeypatch):
    _install_pipeline_stubs(monkeypatch)

    model = DummyModel(["User-A1B2 sugeriu algo importante."])
    reviewed = pipeline._run_privacy_review(
        model,
        newsletter_text="João (User-A1B2) sugeriu algo.",
    )

    assert "João" not in reviewed
    assert "User-A1B2" in reviewed