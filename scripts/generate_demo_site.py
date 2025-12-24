"""Generate the public demo MkDocs site deterministically (no external API calls).

This script is intended for CI/GitHub Pages deployment. It runs the normal
WhatsApp->blog pipeline against the small fixture ZIP in `tests/fixtures/`,
but patches networked components (Gemini, RAG, enrichment, background tasks)
to deterministic stubs so the demo can build without secrets.

It invokes the pipeline via the CLI entry point (`egregora write`) to ensure
stability and realistic usage.
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import frontmatter
import yaml
from pydantic_ai.models.test import TestModel
from typer.testing import CliRunner

from egregora.cli.main import app
from egregora.output_adapters.mkdocs.scaffolding import safe_yaml_load


class WriterDemoModel(TestModel):
    """Deterministic writer model that always emits a single stub post."""

    def __init__(self, *, window_label: str) -> None:
        super().__init__(call_tools=["write_post_tool"])
        self.window_label = window_label

    def gen_tool_args(self, tool_def: Any) -> dict[str, Any]:
        if getattr(tool_def, "name", None) == "write_post_tool":
            safe_label = self.window_label.replace(" ", "-").replace(":", "")
            return {
                "metadata": {
                    "title": f"Egregora Demo — {self.window_label}",
                    "slug": f"{safe_label}-demo",
                    "date": "2025-10-28",
                    "tags": ["demo", "stub"],
                    "authors": ["egregora"],
                    "summary": "Deterministic demo content generated in CI (no API calls).",
                },
                "content": (
                    "This post was generated deterministically during CI to keep the public demo "
                    "updated without requiring API keys.\n\n"
                    "It exercises the full pipeline (parsing, windowing, publishing) while "
                    "stubbing out networked LLM calls."
                ),
            }
        return super().gen_tool_args(tool_def)


@dataclass(frozen=True)
class PatchSpec:
    target: str
    value: object
    optional: bool = False


def _set_attr(dotted: str, value: object, *, optional: bool = False) -> None:
    module_path, attr = dotted.rsplit(".", 1)
    try:
        module = importlib.import_module(module_path)
    except Exception:
        if optional:
            return
        raise
    if not hasattr(module, attr):
        if optional:
            return
        msg = f"Patch target missing: {dotted}"
        raise AttributeError(msg)
    setattr(module, attr, value)


def _apply_patches(patches: list[PatchSpec]) -> None:
    for patch in patches:
        _set_attr(patch.target, patch.value, optional=patch.optional)


def _patch_pipeline_for_offline_demo() -> None:
    # Patch writer to force TestModel usage (no Gemini calls).
    from egregora.agents import writer as writer_agent_module

    original_writer = writer_agent_module.write_posts_with_pydantic_agent

    async def _writer_wrapper(*, prompt: str, config, context, test_model=None):
        return await original_writer(
            prompt=prompt,
            config=config,
            context=context,
            test_model=WriterDemoModel(window_label=context.window_label),
        )

    def _mock_index_documents(documents, **_kwargs):
        return len(documents or [])

    def _mock_search(_query, **_kwargs):
        return SimpleNamespace(hits=[])

    async def _stub_url_enrichment_async(_agent, url, prompts_dir=None) -> str:
        return f"Stub enrichment for {url}"

    async def _stub_media_enrichment_async(_agent, file_path, mime_hint=None, prompts_dir=None) -> str:
        return f"Stub enrichment for {file_path}"

    async def _stub_generate_profile_posts(ctx, messages, window_date) -> list:
        return []

    def _stub_process_avatar_commands(messages_table, context) -> dict:
        return {}

    def _stub_url_agent(_model, _simple=True):
        return object()

    def _stub_media_agent(_model, _simple=False):
        return object()

    def _skip_background_tasks(_ctx) -> None:
        return None

    def _stub_generate_taxonomy(dataset) -> None:
        return None

    patches = [
        # Writer Agent
        PatchSpec("egregora.agents.writer.write_posts_with_pydantic_agent", _writer_wrapper),
        # Disable API key validation for offline demo builds.
        PatchSpec("egregora.utils.env.validate_gemini_api_key", lambda *_args, **_kwargs: None),
        PatchSpec(
            "egregora.orchestration.pipelines.write._validate_api_key",
            lambda _output_dir: None,
            optional=True,
        ),
        # Profile Generator
        PatchSpec(
            "egregora.agents.profile.generator.generate_profile_posts", _stub_generate_profile_posts
        ),
        # Avatar processing
        PatchSpec("egregora.agents.avatar.process_avatar_commands", _stub_process_avatar_commands),

        PatchSpec(
            "egregora.orchestration.pipelines.write._process_background_tasks",
            _skip_background_tasks,
            optional=True,
        ),
        # Taxonomy
        PatchSpec(
            "egregora.orchestration.pipelines.write._generate_taxonomy",
            _stub_generate_taxonomy,
            optional=True,
        ),
        PatchSpec(
            "egregora.ops.taxonomy.generate_semantic_taxonomy", lambda *args, **kwargs: 0, optional=True
        ),
        # RAG: avoid DB creation and searches.
        PatchSpec("egregora.rag.index_documents", _mock_index_documents),
        PatchSpec("egregora.rag.search", _mock_search),
        PatchSpec("egregora.rag.reset_backend", lambda **_kwargs: None),
        PatchSpec(
            "egregora.orchestration.pipelines.write.index_documents", _mock_index_documents, optional=True
        ),
        PatchSpec(
            "egregora.orchestration.pipelines.write.reset_backend", lambda **_kwargs: None, optional=True
        ),
        PatchSpec("egregora.agents.writer_helpers.search", _mock_search, optional=True),
        PatchSpec("egregora.agents.writer.index_documents", _mock_index_documents, optional=True),
        PatchSpec("egregora.agents.writer.reset_backend", lambda **_kwargs: None, optional=True),
        # Enrichment: avoid network and multimodal calls.
        PatchSpec(
            "egregora.agents.enricher.create_url_enrichment_agent", _stub_url_agent, optional=True
        ),
        PatchSpec(
            "egregora.agents.enricher.create_media_enrichment_agent", _stub_media_agent, optional=True
        ),
        PatchSpec(
            "egregora.agents.enricher._run_url_enrichment_async", _stub_url_enrichment_async, optional=True
        ),
        PatchSpec(
            "egregora.agents.enricher._run_media_enrichment_async",
            _stub_media_enrichment_async,
            optional=True,
        ),
    ]

    _apply_patches(patches)


def _rewrite_site_url(mkdocs_config_path: Path, site_url: str) -> None:
    if not mkdocs_config_path.exists():
        return
    text = mkdocs_config_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    replaced = False
    for idx, line in enumerate(lines):
        if line.startswith("site_url:"):
            lines[idx] = f"site_url: {site_url}"
            replaced = True
            break
    if not replaced:
        lines.insert(0, f"site_url: {site_url}")
    mkdocs_config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_demo_config(config_path: Path, max_windows: int) -> None:
    """Harden demo config to avoid network/DB side effects during CI."""
    if not config_path.exists():
        return

    with config_path.open("r", encoding="utf-8") as f:
        data = safe_yaml_load(f.read()) or {}

    # Disable RAG and Writer banners
    if "rag" in data:
        if isinstance(data["rag"], dict):
            data["rag"]["enabled"] = False
    if "writer" in data:
        if isinstance(data["writer"], dict):
            data["writer"]["enable_banners"] = False

    # Set max windows
    if "pipeline" not in data or not isinstance(data["pipeline"], dict):
        data["pipeline"] = {}
    data["pipeline"]["max_windows"] = max_windows

    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def _write_stub_file(path: Path, title: str, content: str) -> None:
    """Write a stub markdown file using python-frontmatter."""
    post = frontmatter.Post(content, title=title)
    path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")


def _inject_demo_build_info(
    index_path: Path, build_timestamp: str, build_commit: str, build_workflow_url: str
) -> None:
    """Inject build provenance into the demo homepage without clobbering content."""
    if not index_path.exists():
        return
    content = index_path.read_text(encoding="utf-8")
    marker_start = "<!-- demo-build-info:start -->"
    marker_end = "<!-- demo-build-info:end -->"
    block = "\n".join(
        [
            marker_start,
            "",
            "> **Demo build**",
            f"> - Generated: {build_timestamp}",
            f"> - Commit: {build_commit}",
            f"> - Workflow: {build_workflow_url}",
            "",
            marker_end,
            "",
        ]
    )

    if marker_start in content and marker_end in content:
        pre, _rest = content.split(marker_start, 1)
        _old, post = _rest.split(marker_end, 1)
        content = f"{pre}{block}{post.lstrip()}"
    else:
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) == 3:
                header = f"---{parts[1]}---\n"
                body = parts[2].lstrip("\n")
                content = f"{header}\n{block}{body}"
            else:
                content = f"{block}{content}"
        else:
            content = f"{block}{content}"

    index_path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/demo"),
        help="Directory to generate the demo MkDocs project into",
    )
    parser.add_argument(
        "--fixture-zip",
        type=Path,
        default=Path("tests/fixtures/Conversa do WhatsApp com Teste.zip"),
        help="WhatsApp export ZIP fixture to use",
    )
    parser.add_argument(
        "--site-url",
        type=str,
        default="https://franklinbaldo.github.io/egregora/demo/",
        help="Final public URL of the demo site (used by MkDocs for canonical links)",
    )
    parser.add_argument(
        "--max-windows",
        type=int,
        default=1,
        help="Limit windows processed for the demo (keeps CI fast)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    output_dir = (repo_root / args.output_dir).resolve()
    fixture_zip = (repo_root / args.fixture_zip).resolve()

    if not fixture_zip.exists():
        msg = f"Fixture ZIP not found: {fixture_zip}"
        raise SystemExit(msg)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Ensure the pipeline doesn't require secrets.
    os.environ.setdefault("GOOGLE_API_KEY", "demo-offline-key")

    _patch_pipeline_for_offline_demo()

    # Pre-scaffold logic is handled by 'egregora write' via 'init' if missing,
    # but to customize the stub files (Journal/Profiles placeholders), we do it beforehand.
    from egregora.output_adapters.mkdocs.scaffolding import ensure_mkdocs_project

    ensure_mkdocs_project(output_dir, site_name="Egregora Demo")

    docs_dir = output_dir / "docs"
    (docs_dir / "journal").mkdir(parents=True, exist_ok=True)
    (docs_dir / "profiles").mkdir(parents=True, exist_ok=True)
    (docs_dir / "media").mkdir(parents=True, exist_ok=True)

    build_timestamp = os.getenv("BUILD_TIMESTAMP", "Unknown")
    build_commit = os.getenv("BUILD_COMMIT", "Unknown")
    build_workflow_url = os.getenv("BUILD_WORKFLOW_URL", "")

    _write_stub_file(
        docs_dir / "journal" / "index.md",
        "Journal",
        "(Reserved for future demo content.)",
    )
    _write_stub_file(
        docs_dir / "profiles" / "index.md",
        "Profiles",
        "(Reserved for future demo content.)",
    )
    _write_stub_file(
        docs_dir / "media" / "index.md",
        "Media",
        "See the demo media gallery at `posts/media/`.",
    )

    mkdocs_config = output_dir / ".egregora" / "mkdocs.yml"
    if mkdocs_config.exists():
        _rewrite_site_url(mkdocs_config, args.site_url)

    config_path = output_dir / ".egregora" / "config.yml"
    # Also check .toml as recent versions might use TOML
    # The generated config is usually .egregora.toml now (v3).
    # Since we don't have a safe toml writer loaded, we skip toml config hacking for now
    # relying on CLI args to disable things (e.g. --no-enable-enrichment).
    # The 'egregora write' command arguments cover most needs (max_prompt_tokens, enable_enrichment).
    # Disabling banner generation specifically isn't a CLI arg, but we patch
    # 'is_banner_generation_available' in _patch_pipeline_for_offline_demo anyway.
    # So we don't strictly need to rewrite .egregora.toml to be safe.

    if config_path.exists():
        _update_demo_config(config_path, args.max_windows)

    # Invoke the CLI using CliRunner
    runner = CliRunner()

    # Arguments for 'egregora write'
    cli_args = [
        "write",
        str(fixture_zip),
        "--output-dir",
        str(output_dir),
        "--step-size",
        "10000",
        "--step-unit",
        "messages",
        "--overlap",
        "0.0",
        "--no-enable-enrichment",
        "--max-prompt-tokens",
        "50000",
        # Force refresh to ensure clean run
        "--force",
    ]


    # Run in-process
    result = runner.invoke(app, cli_args, catch_exceptions=False)

    if result.exit_code != 0:
        if result.output:
            sys.stderr.write(result.output)
        if result.exc_info:
            raise result.exc_info[1]
        return result.exit_code

    _inject_demo_build_info(docs_dir / "index.md", build_timestamp, build_commit, build_workflow_url)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
