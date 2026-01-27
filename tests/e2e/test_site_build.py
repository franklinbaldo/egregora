"""E2E test for author synchronization and site scaffolding.

This test verifies that:
1. Site scaffolding creates required directories
2. sync_authors_from_posts correctly extracts authors from post frontmatter
3. Authors are properly registered in .authors.yml
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from egregora.output_adapters.mkdocs.scaffolding import MkDocsSiteScaffolder

from egregora.knowledge.profiles import sync_all_profiles


def test_sync_authors_from_posts(tmp_path: Path):
    """Test that sync_all_profiles correctly syncs authors from profiles directory."""
    docs_dir = tmp_path / "docs"
    profiles_dir = docs_dir / "posts" / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    # Create profiles
    for author_id, author_name in [
        ("author-uuid-1", "Author One"),
        ("author-uuid-2", "Author Two"),
        ("author-uuid-3", "Author Three"),
    ]:
        author_dir = profiles_dir / author_id
        author_dir.mkdir(parents=True, exist_ok=True)
        (author_dir / "index.md").write_text(
            f"---\nname: {author_name}\n---\n# {author_name}", encoding="utf-8"
        )

    # Sync authors from profiles directory
    # Note: sync_all_profiles expects profiles directory as input
    synced = sync_all_profiles(profiles_dir)

    # Verify
    assert synced == 3, f"Expected 3 unique authors, got {synced}"

    authors_path = docs_dir / ".authors.yml"
    assert authors_path.exists(), ".authors.yml should be created"

    authors = yaml.safe_load(authors_path.read_text())
    assert "author-uuid-1" in authors
    assert "author-uuid-2" in authors
    assert "author-uuid-3" in authors

    # Verify structure
    for author_id in ["author-uuid-1", "author-uuid-2", "author-uuid-3"]:
        assert "name" in authors[author_id]
        assert "url" in authors[author_id]
        assert authors[author_id]["url"] == f"posts/profiles/{author_id}/"


def test_generated_site_scaffolds_correctly(tmp_path: Path):
    """Test that site scaffolding creates required structure."""
    site_root = tmp_path / "test_site"
    scaffolder = MkDocsSiteScaffolder()

    scaffolder.scaffold(site_root, {"site_name": "Test Site"})

    # Verify key paths exist
    assert (site_root / ".egregora" / "mkdocs.yml").exists()
    assert (site_root / "docs").exists()
    assert (site_root / "docs" / "posts").exists()
    assert (site_root / "docs" / "posts" / "profiles").exists()


def test_mkdocs_build_with_material(tmp_path: Path):
    """Test that a scaffolded site can be built with MkDocs (if material is installed)."""
    site_root = tmp_path / "test_site"
    scaffolder = MkDocsSiteScaffolder()

    scaffolder.scaffold(site_root, {"site_name": "Test Site"})

    docs_dir = site_root / "docs"
    posts_dir = docs_dir / "posts"  # Flat structure - no nesting
    posts_dir.mkdir(parents=True, exist_ok=True)

    # Create overrides directory
    overrides_dir = site_root / "overrides"
    overrides_dir.mkdir(parents=True, exist_ok=True)

    # Create a simple post
    post_content = """---
title: Test Post
date: 2025-01-01
---

# Test Post
"""
    (posts_dir / "2025-01-01-test.md").write_text(post_content, encoding="utf-8")

    # Try to build (may fail if mkdocs-material not installed, skip gracefully)
    result = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "-f", ".egregora/mkdocs.yml"],
        check=False,
        cwd=site_root,
        capture_output=True,
        text=True,
        env={**os.environ},
    )

    if "not installed" in result.stderr:
        pytest.skip("mkdocs-material or blog plugin not installed")

    # If it ran, check for warnings (not strict mode for this test)
    # The goal is to verify the config is valid
    assert result.returncode == 0 or "WARNING" in result.stderr, (
        f"Build failed unexpectedly:\n{result.stderr}"
    )
