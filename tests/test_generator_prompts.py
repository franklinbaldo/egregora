from unittest.mock import MagicMock

from egregora.config import PipelineConfig
from egregora.generator import PostGenerator, PromptTemplates


def test_system_instruction_includes_privacy_rules(monkeypatch):
    templates = PromptTemplates(
        group_name_label="Grupo",
        today_label="Hoje",
        previous_post_header="Anterior",
        previous_post_missing="Sem post anterior",
        enrichment_header="Enriquecimento",
        rag_header="RAG",
        transcript_header_single="Transcript {count}",
        transcript_header_multiple="Transcripts {count}",
    )

    monkeypatch.setattr("egregora.generator.GeminiManager", MagicMock())
    monkeypatch.setattr(
        "egregora.generator.PromptLoader.load_text", lambda self, name: f"PROMPT: {name}"
    )
    monkeypatch.setattr(
        "egregora.generator.load_prompt_templates", lambda language, loader: templates
    )

    generator = PostGenerator(PipelineConfig())

    base_instruction = generator._build_system_instruction(has_group_tags=False)
    assert base_instruction
    assert "PROMPT: system_instruction_base.md" in base_instruction[0].text
    assert "multigroup" not in base_instruction[0].text

    multi_instruction = generator._build_system_instruction(has_group_tags=True)
    assert multi_instruction
    assert "PROMPT: system_instruction_base.md" in multi_instruction[0].text
    assert "PROMPT: system_instruction_multigroup.md" in multi_instruction[0].text
