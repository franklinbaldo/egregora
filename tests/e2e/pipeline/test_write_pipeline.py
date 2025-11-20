"""E2E tests for write pipeline orchestration.

These tests validate the full pipeline orchestration from ingestion through
post generation, using mocked writer agents for deterministic execution.

Tests in this file use `process_whatsapp_export` and verify:
- Pipeline completes without errors
- Directory structure is created correctly
- Date range filtering works
- Error handling (missing media, etc.)
"""

from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from egregora.orchestration.write_pipeline import (
    WhatsAppProcessOptions,
    process_whatsapp_export,
)

if TYPE_CHECKING:
    from conftest import WhatsAppFixture


def create_export_from_fixture(fixture: WhatsAppFixture):
    return fixture.create_export()


def _bootstrap_site(tmp_path: Path) -> Path:
    """Bootstrap a test site with MODERN structure (content at root level)."""
    site_root = tmp_path / "site"
    posts_dir = site_root / "posts"
    profiles_dir = site_root / "profiles"
    media_dir = site_root / "media"

    posts_dir.mkdir(parents=True)
    profiles_dir.mkdir(parents=True)
    media_dir.mkdir(parents=True)

    # MODERN: mkdocs.yml in .egregora/ with docs_dir: ..
    egregora_dir = site_root / ".egregora"
    egregora_dir.mkdir(parents=True)
    mkdocs_path = egregora_dir / "mkdocs.yml"
    mkdocs_path.write_text("site_name: Test Suite\ndocs_dir: ..\n", encoding="utf-8")
    return site_root


class DummyGenaiClient:
    """Dummy Google GenAI client for testing.

    Supports:
    - Pydantic-AI agent calls (models.generate_content)
    - File uploads (files.upload)
    - Embeddings (models.embed_content)
    """

    def __init__(self, *args, **kwargs):
        # Response for pydantic-ai agents - needs text attribute
        def dummy_generate(*a, **k):
            return SimpleNamespace(
                text='{"markdown": "Test enrichment content"}',
                candidates=[
                    SimpleNamespace(
                        content=SimpleNamespace(
                            parts=[SimpleNamespace(text='{"markdown": "Test enrichment content"}')]
                        )
                    )
                ],
            )

        # Embedding response
        def dummy_embed(*a, **k):
            return SimpleNamespace(embedding=SimpleNamespace(values=[0.1] * 768))

        self.models = SimpleNamespace(
            generate_content=dummy_generate,
            embed_content=dummy_embed,
        )
        self.aio = SimpleNamespace(models=self.models)

        # File upload support
        def dummy_upload(*a, **k):
            return SimpleNamespace(
                uri="stub://file",
                mime_type="image/jpeg",
                name="stub-file",
                state=SimpleNamespace(name="ACTIVE"),
            )

        self.files = SimpleNamespace(
            upload=dummy_upload,
            get=lambda name: SimpleNamespace(
                uri="stub://file", mime_type="image/jpeg", name=name, state=SimpleNamespace(name="ACTIVE")
            ),
        )

    def close(self):  # pragma: no cover - compatibility shim
        return None


def _install_pipeline_stubs(monkeypatch, captured_dates: list[str]):
    monkeypatch.setattr("egregora.orchestration.write_pipeline.genai.Client", DummyGenaiClient)
    # Note: GeminiDispatcher has been removed - pipeline now uses genai.Client directly

    # We need to mock the agent's behavior without bypassing the orchestration logic.
    # We do this by patching `_setup_agent_and_state` to return an agent using a TestModel.
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel

    from egregora.agents.writer.agent import (
        WriterAgentReturn,
        WriterAgentState,
        _create_writer_agent_state,
    )
    from egregora.agents.writer.tools import register_writer_tools

    def _stub_agent_setup(config, context, test_model=None):
        window_label = f"{context.start_time:%Y-%m-%d %H:%M} to {context.end_time:%H:%M}"
        captured_dates.append(window_label)

        # We need to register tools so the TestModel can 'call' them (simulated)
        # However, TestModel generates random tool calls by default unless configured.
        # Let's override gen_tool_args in a subclass for deterministic behavior.

        class DeterministicTestModel(TestModel):
            def gen_tool_args(self, tool_def):
                if tool_def.name == "write_post_tool":
                    return {
                        "metadata": {
                            "title": f"Stub Post for {window_label}",
                            "slug": f"{context.start_time:%Y%m%d_%H%M%S}-stub",
                            "date": f"{context.start_time:%Y-%m-%d}",
                            "tags": [],
                            "authors": ["system"],
                            "summary": "Stub summary"
                        },
                        "content": "This is a placeholder post used during testing."
                    }
                return super().gen_tool_args(tool_def)

        agent = Agent[WriterAgentState, WriterAgentReturn](
            model=DeterministicTestModel(call_tools=["write_post_tool"]),
            deps_type=WriterAgentState
        )

        # Register real tools so the agent can actually execute them (writing files)
        register_writer_tools(agent, enable_banner=False, enable_rag=False)

        state = _create_writer_agent_state(context, config)
        return agent, state, window_label

    monkeypatch.setattr("egregora.agents.writer.agent._setup_agent_and_state", _stub_agent_setup)


# =============================================================================
# Pipeline Orchestration Tests
# =============================================================================


@pytest.mark.xfail(reason="Path resolution mismatch in test environment vs pipeline validation")
def test_full_pipeline_completes_without_crash(
    whatsapp_fixture: WhatsAppFixture,
    tmp_path: Path,
    monkeypatch,
    gemini_api_key: str,
):
    """Test that the full pipeline executes without errors.

    This test validates:
    - Pipeline processes all windows
    - No exceptions are raised
    - Expected date ranges are processed
    """
    site_root = _bootstrap_site(tmp_path)
    processed_dates: list[str] = []
    _install_pipeline_stubs(monkeypatch, processed_dates)

    options = WhatsAppProcessOptions(
        output_dir=site_root,
        step_size=100,
        step_unit="messages",
        enable_enrichment=False,
        timezone=whatsapp_fixture.timezone,
        gemini_api_key=gemini_api_key,
    )

    results = process_whatsapp_export(
        whatsapp_fixture.zip_path,
        options=options,
    )

    assert results
    assert processed_dates == ["2025-10-28 14:10 to 14:15"]


@pytest.mark.xfail(reason="Path resolution mismatch in test environment vs pipeline validation")
def test_pipeline_creates_expected_directory_structure(
    whatsapp_fixture: WhatsAppFixture,
    tmp_path: Path,
    monkeypatch,
    gemini_api_key: str,
):
    """Test that pipeline creates correct output directory structure.

    This test validates:
    - Posts directory is created
    - Profiles directory is created
    - Media directory is created
    - .egregora config directory is created
    """
    site_root = _bootstrap_site(tmp_path)
    _install_pipeline_stubs(monkeypatch, [])

    options = WhatsAppProcessOptions(
        output_dir=site_root,
        step_size=100,
        step_unit="messages",
        enable_enrichment=False,
        timezone=whatsapp_fixture.timezone,
        gemini_api_key=gemini_api_key,
    )

    process_whatsapp_export(
        whatsapp_fixture.zip_path,
        options=options,
    )

    # MODERN: content at root level, not in docs/
    assert (site_root / "posts").exists()
    assert (site_root / "profiles").exists()
    assert (site_root / "media").exists()
    assert (site_root / ".egregora").exists()


@pytest.mark.xfail(reason="Path resolution mismatch in test environment vs pipeline validation")
def test_pipeline_respects_date_range_filters(
    whatsapp_fixture: WhatsAppFixture,
    tmp_path: Path,
    monkeypatch,
    gemini_api_key: str,
):
    """Test that pipeline correctly filters messages by date range.

    This test validates:
    - Messages outside date range are not processed
    - No windows are created when all messages filtered out
    - Empty results returned when no data to process
    """
    site_root = _bootstrap_site(tmp_path)
    processed_dates: list[str] = []
    _install_pipeline_stubs(monkeypatch, processed_dates)

    options = WhatsAppProcessOptions(
        output_dir=site_root,
        step_size=100,
        step_unit="messages",
        enable_enrichment=False,
        from_date=date(2025, 10, 29),
        to_date=date(2025, 10, 29),
        timezone=whatsapp_fixture.timezone,
        gemini_api_key=gemini_api_key,
    )

    results = process_whatsapp_export(
        whatsapp_fixture.zip_path,
        options=options,
    )

    assert results == {}
    assert processed_dates == []


@pytest.mark.xfail(reason="Path resolution mismatch in test environment vs pipeline validation")
def test_pipeline_handles_missing_media_gracefully(
    whatsapp_fixture: WhatsAppFixture,
    tmp_path: Path,
    monkeypatch,
    gemini_api_key: str,
):
    """Test that pipeline handles missing media files without crashing.

    This test validates:
    - Pipeline completes even when referenced media is missing
    - No exceptions raised for missing files
    - Results are still generated
    """
    corrupted_zip = tmp_path / "corrupted.zip"
    with (
        zipfile.ZipFile(whatsapp_fixture.zip_path) as source,
        zipfile.ZipFile(corrupted_zip, "w") as target,
    ):
        for info in source.infolist():
            if info.filename.endswith("WA0035.jpg"):
                continue
            target.writestr(info, source.read(info))

    site_root = _bootstrap_site(tmp_path)
    _install_pipeline_stubs(monkeypatch, [])

    options = WhatsAppProcessOptions(
        output_dir=site_root,
        step_size=100,
        step_unit="messages",
        enable_enrichment=False,
        timezone=whatsapp_fixture.timezone,
        gemini_api_key=gemini_api_key,
    )

    results = process_whatsapp_export(
        corrupted_zip,
        options=options,
    )

    assert results is not None
