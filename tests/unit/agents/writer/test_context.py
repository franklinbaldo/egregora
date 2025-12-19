"""Unit tests for writer context module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ibis import memtable

from egregora.agents.writer.context import (
    WriterContext,
    WriterContextParams,
    _build_context_and_signature,
    _build_writer_context,
    _truncate_for_embedding,
    inject_profiles_context,
    inject_rag_context,
)
from egregora.config.settings import EgregoraConfig


class TestWriterContext:
    def test_truncate_for_embedding(self):
        text = "a" * 100
        truncated = _truncate_for_embedding(text, byte_limit=50)
        # 50 chars + 34 chars for comment = 84
        assert len(truncated) <= 84
        assert "truncated" in truncated

        short_text = "short"
        assert _truncate_for_embedding(short_text, byte_limit=50) == short_text

    @patch("egregora.agents.writer.context.build_conversation_xml")
    @patch("egregora.agents.writer.context.load_journal_memory")
    @patch("egregora.agents.writer.context.get_active_authors")
    def test_build_writer_context(
        self, mock_active_authors, mock_journal, mock_xml
    ):
        # Mocks
        mock_xml.return_value = "<xml>conversation</xml>"
        mock_journal.return_value = "Journal content"
        mock_active_authors.return_value = ["author1"]

        mock_table = MagicMock()
        mock_table.to_pyarrow.return_value = "pyarrow_table"

        mock_resources = MagicMock()
        mock_resources.output.get_format_instructions.return_value = "Format instructions"

        config = EgregoraConfig()
        config.writer.custom_instructions = "Custom instructions"
        config.privacy.pii_detection_enabled = True

        params = WriterContextParams(
            table=mock_table,
            resources=mock_resources,
            cache=MagicMock(),
            config=config,
            window_label="Window 1",
            adapter_content_summary="Summary",
            adapter_generation_instructions="Gen instructions",
        )

        ctx = _build_writer_context(params)

        assert ctx.conversation_xml == "<xml>conversation</xml>"
        assert ctx.journal_memory == "Journal content"
        assert ctx.active_authors == ["author1"]
        assert ctx.format_instructions == "Format instructions"
        assert "Custom instructions" in ctx.custom_instructions
        assert "Gen instructions" in ctx.custom_instructions
        assert ctx.source_context == "Summary"
        assert ctx.pii_prevention is not None

    def test_writer_context_template_context(self):
        ctx = WriterContext(
            conversation_xml="xml",
            rag_context="rag",
            profiles_context="profiles",
            journal_memory="journal",
            active_authors=["a", "b"],
            format_instructions="format",
            custom_instructions="custom",
            source_context="source",
            date_label="date",
        )

        tpl_ctx = ctx.template_context
        assert tpl_ctx["conversation_xml"] == "xml"
        assert tpl_ctx["active_authors"] == "a, b"
        assert tpl_ctx["enable_memes"] is False

    @patch("egregora.agents.writer.context.build_rag_context_for_prompt")
    def test_inject_rag_context(self, mock_build_rag):
        mock_ctx = MagicMock()
        mock_ctx.deps.resources.retrieval_config.enabled = True
        mock_ctx.deps.resources.retrieval_config.top_k = 3
        mock_ctx.deps.conversation_xml = "content"

        mock_build_rag.return_value = "RAG Results"

        result = inject_rag_context(mock_ctx)
        assert result == "RAG Results"
        mock_build_rag.assert_called_with("content", top_k=3, cache=None)

    def test_inject_rag_context_disabled(self):
        mock_ctx = MagicMock()
        mock_ctx.deps.resources.retrieval_config.enabled = False
        result = inject_rag_context(mock_ctx)
        assert result == ""

    @patch("egregora.agents.writer.context.load_profiles_context")
    def test_inject_profiles_context(self, mock_load_profiles):
        mock_ctx = MagicMock()
        mock_ctx.deps.active_authors = ["a1"]
        mock_ctx.deps.resources.output = "output"

        mock_load_profiles.return_value = "Profiles"

        result = inject_profiles_context(mock_ctx)
        assert result == "Profiles"
        mock_load_profiles.assert_called_with(["a1"], "output")

    @patch("egregora.agents.writer.context._build_writer_context")
    @patch("egregora.agents.writer.context.PromptManager")
    @patch("egregora.agents.writer.context.generate_window_signature")
    def test_build_context_and_signature(self, mock_sig, mock_pm, mock_build_ctx):
        mock_pm.get_template_content.return_value = "template"
        mock_build_ctx.return_value = MagicMock(conversation_xml="xml")
        mock_sig.return_value = "signature_hash"

        # Create a real ibis table to test casting (or mock it properly)
        # Using a mock for simplicity as casting logic relies on ibis internals
        mock_table = MagicMock()

        params = WriterContextParams(
            table=mock_table,
            resources=MagicMock(),
            cache=MagicMock(),
            config=EgregoraConfig(),
            window_label="w1",
            adapter_content_summary="",
            adapter_generation_instructions="",
        )

        ctx, sig = _build_context_and_signature(params, None)

        assert sig == "signature_hash"
        # Verify table mutation was attempted (checking if mutate called)
        mock_table.mutate.assert_called()
