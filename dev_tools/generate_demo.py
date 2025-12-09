"""Regenerate the docs/demo blog with real pipeline calls.

This script is intentionally thin: it shells out to the public CLI so the
end-to-end path mirrors what contributors do locally:

1. `egregora init docs/demo --no-interactive`
2. `egregora write "tests/fixtures/Conversa do WhatsApp com Teste.zip" --output-dir docs/demo`

Set `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) in your environment before running.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from google import genai
import yaml

from egregora.utils.env import get_google_api_key

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = PROJECT_ROOT / "docs" / "demo"
INPUT_ZIP = PROJECT_ROOT / "tests" / "fixtures" / "Conversa do WhatsApp com Teste.zip"
CONFIG_DIR = DEMO_ROOT / ".egregora"
CONFIG_PATH = CONFIG_DIR / "config.yml"
PREFERRED_MKDOCS_PATH = CONFIG_DIR / "mkdocs.yml"
LEGACY_MKDOCS_PATH = DEMO_ROOT / "mkdocs.yml"

MKDOCS_STUB = """site_name: Egregora Demo\nsite_url: https://example.com\ndocs_dir: .\nnav:\n  - Demo: index.md\n"""


def _run(command: list[str]) -> None:
    """Execute a CLI command and stream output live."""
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def _assert_valid_api_key() -> None:
    """Fail fast if the configured Gemini API key is invalid or expired."""

    # Defer import until runtime to avoid impacting environments without the SDK
    api_key = get_google_api_key()
    client = genai.Client(api_key=api_key)

    try:
        # count_tokens is inexpensive and validates the key against the models API
        client.models.count_tokens(model="gemini-1.5-flash", contents="healthcheck")
    except Exception as exc:  # noqa: BLE001 - surface the exact SDK error to the caller
        msg = f"Gemini API key validation failed: {exc}"
        raise SystemExit(msg) from exc


def _ensure_scaffold() -> None:
    """Create a usable MkDocs scaffold when needed.

    The pipeline requires both .egregora/config.yml and a mkdocs.yml. In CI the
    config file already exists, but mkdocs.yml may not; this preflight keeps the
    demo site valid without requiring contributors to delete and re-init.
    """

    mkdocs_present = PREFERRED_MKDOCS_PATH.exists() or LEGACY_MKDOCS_PATH.exists()
    if not CONFIG_PATH.exists():
        _run(["uv", "run", "egregora", "init", str(DEMO_ROOT), "--no-interactive"])

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # If mkdocs.yml is missing, write a minimal stub so the pipeline passes its
    # preflight validation without altering existing demo content.
    if not mkdocs_present:
        PREFERRED_MKDOCS_PATH.write_text(MKDOCS_STUB, encoding="utf-8")
        if not LEGACY_MKDOCS_PATH.exists():
            LEGACY_MKDOCS_PATH.symlink_to(PREFERRED_MKDOCS_PATH.relative_to(DEMO_ROOT))


def _ensure_paths_config() -> None:
    """Ensure the demo config keeps content inside docs/demo."""
    config = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    config.setdefault("paths", {})
    config["paths"].update(
        {
            "docs_dir": ".",
            "posts_dir": ".",
            "profiles_dir": "profiles",
            "media_dir": "media",
            "journal_dir": "journal",
        }
    )
    CONFIG_PATH.write_text(yaml.safe_dump(config, sort_keys=False))


def _clean_generated_content() -> None:
    """Remove generated markdown so the next write run is fresh."""
    posts_dir = DEMO_ROOT / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)
    for markdown in posts_dir.glob("*.md"):
        markdown.unlink()


if __name__ == "__main__":
    if not INPUT_ZIP.exists():
        raise SystemExit(f"Missing demo input: {INPUT_ZIP}")

    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        raise SystemExit("Set GEMINI_API_KEY or GOOGLE_API_KEY before regenerating the demo site.")

    os.environ.setdefault("PYTHONWARNINGS", "ignore")

    # Validate the key before mutating the demo checkout or running the pipeline
    _assert_valid_api_key()

    # 1) Scaffold the demo site once; skip if existing scaffold is usable.
    _ensure_scaffold()

    # 2) Force the paths so Material blogging picks up the generated posts.
    _ensure_paths_config()

    # 3) Clear previously generated posts and regenerate from the sample export.
    _clean_generated_content()
    _run(
        [
            "uv",
            "run",
            "egregora",
            "write",
            str(INPUT_ZIP),
            "--output-dir",
            str(DEMO_ROOT),
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
        ]
    )

    print("Demo blog regenerated in docs/demo/posts")
