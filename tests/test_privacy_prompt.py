from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.config import PipelineConfig
from egregora.generator import NewsletterGenerator


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
    monkeypatch.setattr(
        NewsletterGenerator, "_load_prompt", lambda self, name: f"PROMPT: {name}"
    )


def test_system_instruction_includes_privacy_rules(monkeypatch):
    _install_generator_stubs(monkeypatch)
    config = PipelineConfig.with_defaults()
    generator = NewsletterGenerator(config)

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
