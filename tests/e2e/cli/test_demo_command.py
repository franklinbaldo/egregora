"""
End-to-end test for the 'egregora demo' CLI command.
"""

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from egregora.cli.main import app

runner = CliRunner()


@pytest.fixture
def clean_demo_dir():
    """Ensure the demo directory is clean before and after the test."""
    demo_path = Path("demo")
    if demo_path.exists():
        shutil.rmtree(demo_path)
    yield demo_path
    if demo_path.exists():
        shutil.rmtree(demo_path)


def test_demo_command_creates_site_structure(clean_demo_dir: Path):
    """
    Tests that the `egregora demo` command successfully creates the site structure,
    even if the content generation pipeline fails (e.g., due to missing API keys).
    """
    result = runner.invoke(app, ["demo"])

    # The command should initialize the site, but the pipeline may fail gracefully (exit code 1)
    # if API keys are not available in the test environment.
    assert result.exit_code in (0, 1), (
        f"CLI command failed unexpectedly with exit code {result.exit_code}: {result.stdout}"
    )

    assert clean_demo_dir.exists(), "The 'demo' directory was not created."
    assert clean_demo_dir.is_dir(), "The 'demo' path is not a directory."

    # Check for core scaffold files
    mkdocs_yml = clean_demo_dir / ".egregora" / "mkdocs.yml"
    assert mkdocs_yml.exists(), "The 'demo/.egregora/mkdocs.yml' file was not created."
    assert mkdocs_yml.is_file(), "The 'demo/.egregora/mkdocs.yml' path is not a file."

    docs_dir = clean_demo_dir / "docs"
    assert docs_dir.exists(), "The 'demo/docs' directory was not created."

    index_md = docs_dir / "index.md"
    assert index_md.exists(), "The 'demo/docs/index.md' file was not created."

    posts_dir = docs_dir / "posts"
    assert posts_dir.exists(), "The 'demo/docs/posts' directory was not created."

    # If the pipeline succeeded, there should be at least one post.
    if result.exit_code == 0:
        # Exclude index.md and tags.md from the post count
        post_files = [p for p in posts_dir.glob("*.md") if p.name not in ("index.md", "tags.md")]
        assert len(post_files) > 0, "Pipeline succeeded but no post files were generated in demo/docs/posts."
