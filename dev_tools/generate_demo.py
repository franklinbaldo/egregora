"""Regenerate the docs/demo blog with real pipeline calls.

This script is intentionally thin: it shells out to the public CLI so the
end-to-end path mirrors what contributors do locally:

1. `egregora init docs/demo --no-interactive`
2. `egregora write "tests/fixtures/Conversa do WhatsApp com Teste.zip" --output-dir docs/demo`

Set `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) in your environment before running.
"""

from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml
from google import genai

from egregora.utils.env import get_google_api_key

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = PROJECT_ROOT / "docs" / "demo"
INPUT_ZIP = PROJECT_ROOT / "tests" / "fixtures" / "Conversa do WhatsApp com Teste.zip"

MKDOCS_STUB = (
    """site_name: Egregora Demo\nsite_url: https://example.com\ndocs_dir: .\nnav:\n  - Demo: index.md\n"""
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DemoPaths:
    """Resolved paths for demo generation."""

    demo_root: Path
    project_root: Path
    config_dir: Path
    config_path: Path
    preferred_mkdocs_path: Path
    legacy_mkdocs_path: Path

    @classmethod
    def from_root(cls, demo_root: Path, project_root: Path = PROJECT_ROOT) -> DemoPaths:
        config_dir = demo_root / ".egregora"
        return cls(
            demo_root=demo_root,
            project_root=project_root,
            config_dir=config_dir,
            config_path=config_dir / "config.yml",
            preferred_mkdocs_path=config_dir / "mkdocs.yml",
            legacy_mkdocs_path=demo_root / "mkdocs.yml",
        )


def _run(command: list[str], *, cwd: Path = PROJECT_ROOT) -> None:
    """Execute a CLI command and stream output live."""
    subprocess.run(command, cwd=cwd, check=True)  # noqa: S603


def _assert_valid_api_key() -> None:
    """Fail fast if the configured Gemini API key is invalid or expired."""
    # Defer import until runtime to avoid impacting environments without the SDK
    api_key = get_google_api_key()
    client = genai.Client(api_key=api_key)

    try:
        # count_tokens is inexpensive and validates the key against the models API
        client.models.count_tokens(model="gemini-1.5-flash", contents="healthcheck")
    except Exception as exc:
        msg = f"Gemini API key validation failed: {exc}"
        raise SystemExit(msg) from exc


def _ensure_scaffold(paths: DemoPaths, run_command: Callable[..., None]) -> None:
    """Create a usable MkDocs scaffold when needed.

    The pipeline requires both .egregora/config.yml and a mkdocs.yml. In CI the
    config file already exists, but mkdocs.yml may not; this preflight keeps the
    demo site valid without requiring contributors to delete and re-init.
    """
    mkdocs_present = paths.preferred_mkdocs_path.exists() or paths.legacy_mkdocs_path.exists()
    if not paths.config_path.exists():
        run_command(
            ["uv", "run", "egregora", "init", str(paths.demo_root), "--no-interactive"],
            cwd=paths.project_root,
        )

    paths.config_dir.mkdir(parents=True, exist_ok=True)

    # If mkdocs.yml is missing, write a minimal stub so the pipeline passes its
    # preflight validation without altering existing demo content.
    if not mkdocs_present:
        paths.preferred_mkdocs_path.write_text(MKDOCS_STUB, encoding="utf-8")
        if not paths.legacy_mkdocs_path.exists():
            paths.legacy_mkdocs_path.symlink_to(paths.preferred_mkdocs_path.relative_to(paths.demo_root))


def _ensure_paths_config(paths: DemoPaths) -> dict:
    """Ensure the demo config keeps content inside docs/demo."""
    config = yaml.safe_load(paths.config_path.read_text()) or {}
    config.setdefault("paths", {})
    config["paths"].update(
        {
            "docs_dir": "docs",
            "posts_dir": "blog/posts",
            "profiles_dir": "profiles",
            "media_dir": "media",
            "journal_dir": "journal",
        }
    )
    paths.config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    return config


def _clean_generated_content(paths: DemoPaths, config: dict) -> Path:
    """Remove generated markdown so the next write run is fresh."""
    docs_dir = paths.demo_root / config["paths"]["docs_dir"]
    posts_dir = docs_dir / config["paths"]["posts_dir"]
    blog_root = posts_dir.parent
    docs_dir.mkdir(parents=True, exist_ok=True)
    blog_root.mkdir(parents=True, exist_ok=True)
    posts_dir.mkdir(parents=True, exist_ok=True)
    for markdown in posts_dir.glob("*.md"):
        markdown.unlink()

    return posts_dir


def regenerate_demo(
    *,
    demo_root: Path = DEMO_ROOT,
    input_zip: Path = INPUT_ZIP,
    validate_api_key: bool = True,
    run_command: Callable[..., None] = _run,
    project_root: Path = PROJECT_ROOT,
) -> None:
    """Regenerate the demo blog using the public CLI."""
    if not input_zip.exists():
        message = f"Missing demo input: {input_zip}"
        raise SystemExit(message)

    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        message = "Set GEMINI_API_KEY or GOOGLE_API_KEY before regenerating the demo site."
        raise SystemExit(message)

    os.environ.setdefault("PYTHONWARNINGS", "ignore")

    if validate_api_key:
        _assert_valid_api_key()

    paths = DemoPaths.from_root(demo_root, project_root)

    # 1) Scaffold the demo site once; skip if existing scaffold is usable.
    _ensure_scaffold(paths, run_command)

    # 2) Force the paths so Material blogging picks up the generated posts.
    config = _ensure_paths_config(paths)

    # 3) Clear previously generated posts and regenerate from the sample export.
    posts_dir = _clean_generated_content(paths, config)
    run_command(
        [
            "uv",
            "run",
            "egregora",
            "write",
            str(input_zip),
            "--output-dir",
            str(paths.demo_root),
            "--source-type",
            "whatsapp",
            "--step-unit",
            "days",
            "--step-size",
            "1",
            "--max-windows",
            "1",
            "--timezone",
            "America/Sao_Paulo",
        ],
        cwd=paths.project_root,
    )
    logger.info("Demo blog regenerated in %s", posts_dir)


if __name__ == "__main__":
    regenerate_demo()
