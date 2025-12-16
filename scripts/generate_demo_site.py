"""Generate the public demo MkDocs site deterministically (no external API calls).

This script is intended for CI/GitHub Pages deployment. It runs the normal
WhatsApp->blog pipeline against the small fixture ZIP in `tests/fixtures/`,
but patches networked components (Gemini, RAG, enrichment, background tasks)
to deterministic stubs so the demo can build without secrets.
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pydantic_ai.models.test import TestModel


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
    from egregora.agents import writer as writer_module

    original_writer = writer_module.write_posts_with_pydantic_agent

    def _writer_wrapper(*, prompt: str, config, context, test_model=None):
        return original_writer(
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

    def _stub_url_agent(_model, _simple=True):
        return object()

    def _stub_media_agent(_model, _simple=False):
        return object()

    def _skip_background_tasks(_ctx) -> None:
        return None

    patches = [
        PatchSpec("egregora.agents.writer.write_posts_with_pydantic_agent", _writer_wrapper),
        # Avoid banner capability and workers.
        PatchSpec("egregora.agents.writer_setup.is_banner_generation_available", lambda: False),
        PatchSpec("egregora.orchestration.pipelines.write._process_background_tasks", _skip_background_tasks),
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
        PatchSpec("egregora.agents.enricher.create_url_enrichment_agent", _stub_url_agent, optional=True),
        PatchSpec("egregora.agents.enricher.create_media_enrichment_agent", _stub_media_agent, optional=True),
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
    text = mkdocs_config_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[str] = []
    replaced = False
    for line in lines:
        if line.strip().startswith("site_url:"):
            out.append(f"site_url: {site_url}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.insert(0, f"site_url: {site_url}")
    mkdocs_config_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _rewrite_pipeline_max_windows(config_path: Path, max_windows: int) -> None:
    text = config_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if any(line.strip().startswith("max_windows:") for line in lines):
        out: list[str] = []
        for line in lines:
            if line.strip().startswith("max_windows:"):
                out.append(f"  max_windows: {max_windows}")
            else:
                out.append(line)
        config_path.write_text("\n".join(out) + "\n", encoding="utf-8")
        return

    out = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and line.strip() == "pipeline:":
            out.append(f"  max_windows: {max_windows}")
            inserted = True
    if not inserted:
        out.extend(["", "pipeline:", f"  max_windows: {max_windows}"])
    config_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _rewrite_demo_config(config_path: Path) -> None:
    """Harden demo config to avoid network/DB side effects during CI."""
    text = config_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[str] = []
    in_rag = False
    in_writer = False
    for line in lines:
        stripped = line.strip()
        if stripped and not line.startswith(" "):
            in_rag = stripped == "rag:"
            in_writer = stripped == "writer:"

        if in_rag and stripped.startswith("enabled:"):
            out.append("  enabled: false")
            continue
        if in_writer and stripped.startswith("enable_banners:"):
            out.append("  enable_banners: false")
            continue
        out.append(line)
    config_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".demo-site"),
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

    from egregora.init import ensure_mkdocs_project
    from egregora.orchestration.pipelines.write import WhatsAppProcessOptions, process_whatsapp_export

    ensure_mkdocs_project(output_dir, site_name="Egregora Demo")

    docs_dir = output_dir / "docs"
    (docs_dir / "journal").mkdir(parents=True, exist_ok=True)
    (docs_dir / "profiles").mkdir(parents=True, exist_ok=True)
    (docs_dir / "media").mkdir(parents=True, exist_ok=True)
    (docs_dir / "journal" / "index.md").write_text(
        "# Journal\n\n(Reserved for future demo content.)\n", encoding="utf-8"
    )
    (docs_dir / "profiles" / "index.md").write_text(
        "# Profiles\n\n(Reserved for future demo content.)\n", encoding="utf-8"
    )
    (docs_dir / "media" / "index.md").write_text(
        "# Media\n\nSee the demo media gallery at `posts/media/`.\n", encoding="utf-8"
    )

    mkdocs_config = output_dir / ".egregora" / "mkdocs.yml"
    if mkdocs_config.exists():
        _rewrite_site_url(mkdocs_config, args.site_url)

    config_path = output_dir / ".egregora" / "config.yml"
    if config_path.exists():
        _rewrite_demo_config(config_path)
        _rewrite_pipeline_max_windows(config_path, args.max_windows)

    options = WhatsAppProcessOptions(
        output_dir=output_dir,
        step_size=10_000,
        step_unit="messages",
        overlap_ratio=0.0,
        enable_enrichment=False,
        gemini_api_key="demo-offline-key",
        max_prompt_tokens=50_000,
    )

    previous_cwd = Path.cwd()
    try:
        os.chdir(output_dir)
        process_whatsapp_export(fixture_zip, options=options)
    finally:
        os.chdir(previous_cwd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
