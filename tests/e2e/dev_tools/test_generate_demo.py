"""End-to-end test for demo generation using mocked LLM responses."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from dev_tools.generate_demo import INPUT_ZIP, regenerate_demo
from egregora import rag
from egregora.agents import enricher, writer
from egregora.init.scaffolding import ensure_mkdocs_project
from egregora.orchestration.write_pipeline import WhatsAppProcessOptions, process_whatsapp_export
from egregora.output_adapters.mkdocs.paths import derive_mkdocs_paths


@pytest.mark.e2e
@pytest.mark.usefixtures("llm_response_mocks", "mock_vector_store", "mocked_writer_agent")
def test_generate_demo_with_mock_llm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run demo generator end-to-end with mocked LLM and embeddings."""

    # Configure environment (skip real key validation but satisfy CLI preflight)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    project_root = Path(__file__).resolve().parents[3]
    demo_root = tmp_path / "demo"
    env = os.environ.copy()
    run_results: dict[str, object] = {}

    monkeypatch.setattr(enricher.EnrichmentWorker, "_load_media_bytes", lambda self, task, payload: b"fake")
    monkeypatch.setattr(
        enricher.EnrichmentWorker, "_execute_media_batch", lambda self, requests, task_map: []
    )

    # Sanity check that RAG operations are patched by the shared fixtures
    assert rag.index_documents.__name__ != "index_documents"
    assert writer.write_posts_with_pydantic_agent.__name__ != "write_posts_with_pydantic_agent"

    def run_command(command: list[str], *, cwd: Path) -> None:
        assert command[:3] == ["uv", "run", "egregora"]
        assert cwd == project_root

        args = command[3:]
        if args[0] == "init":
            ensure_mkdocs_project(Path(args[1]))
            return

        assert args[0] == "write", f"Unexpected command {args}"

        options = WhatsAppProcessOptions(
            output_dir=demo_root,
            timezone="America/Sao_Paulo",
            gemini_api_key=env["GEMINI_API_KEY"],
            step_unit="days",
            step_size=1,
            enable_enrichment=True,
        )

        run_results["result"] = process_whatsapp_export(Path(args[1]), options=options)

    regenerate_demo(
        demo_root=demo_root,
        input_zip=INPUT_ZIP,
        validate_api_key=False,
        run_command=run_command,
        project_root=project_root,
    )

    config_path = demo_root / ".egregora" / "config.yml"
    config = yaml.safe_load(config_path.read_text())

    site_paths = derive_mkdocs_paths(demo_root, config=None)
    posts_dir = site_paths["posts_dir"]

    assert "result" in run_results, "write command did not execute"
    assert run_results["result"], f"Pipeline result was empty: {run_results['result']}"

    assert posts_dir.exists()
    window_posts = next(iter(run_results["result"].values()))["posts"]
    assert window_posts, f"Pipeline should generate at least one post. Result: {run_results['result']}"

    assert config["paths"]["posts_dir"] == "blog/posts"
    assert config["paths"]["docs_dir"] == "docs"
