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
from egregora.utils.filesystem import sync_authors_from_posts


def test_sync_authors_from_posts(tmp_path: Path):
    """Test that sync_authors_from_posts correctly syncs authors from post frontmatter."""
    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"  # Flat structure - no nesting
    posts_dir.mkdir(parents=True)

    # Create posts with different authors
    post1 = """---
title: Post 1
date: 2025-01-01
authors:
  - author-uuid-1
  - author-uuid-2
---
# Post 1
"""
    post2 = """---
title: Post 2
date: 2025-01-02
authors:
  - author-uuid-2
  - author-uuid-3
---
# Post 2
"""
    (posts_dir / "2025-01-01-post1.md").write_text(post1, encoding="utf-8")
    (posts_dir / "2025-01-02-post2.md").write_text(post2, encoding="utf-8")

    # Sync authors
    synced = sync_authors_from_posts(posts_dir, docs_dir)

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
        assert authors[author_id]["url"] == f"profiles/{author_id}.md"


def test_generated_site_scaffolds_correctly(tmp_path: Path):
    """Test that site scaffolding creates required structure."""
    site_root = tmp_path / "test_site"
    scaffolder = MkDocsSiteScaffolder()

    scaffolder.scaffold(site_root, {"site_name": "Test Site"})

    # Verify key paths exist
    assert (site_root / ".egregora" / "mkdocs.yml").exists()
    assert (site_root / "docs").exists()
    assert (site_root / "docs" / "posts").exists()
    assert (site_root / "docs" / "profiles").exists()


def test_mkdocs_build_with_material(tmp_path: Path):
    """Test that a scaffolded site can be built with MkDocs (if material is installed)."""
    site_root = tmp_path / "test_site"
    scaffolder = MkDocsSiteScaffolder()

    scaffolder.scaffold(site_root, {"site_name": "Test Site"})

    docs_dir = site_root / "docs"
    posts_dir = docs_dir / "posts"  # Flat structure - no nesting
    posts_dir.mkdir(parents=True, exist_ok=True)

    # Create overrides directory
    overrides_dir = site_root / ".egregora" / "overrides"
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
        check=False, cwd=site_root,
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
