
"""Benchmarks for SiteGenerator performance."""
import pytest
import frontmatter
from pathlib import Path
from unittest.mock import MagicMock
from egregora.output_adapters.mkdocs.site_generator import SiteGenerator
from egregora.data_primitives.document import DocumentType

# Mock classes
class MockUrlConvention:
    pass

class MockUrlContext:
    pass

@pytest.fixture
def large_site_dir(tmp_path):
    """Create a mock site directory with 100 posts."""
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()

    # Create 100 posts
    for i in range(100):
        content = f"""---
title: Post {i}
date: 2024-01-01
authors:
  - author1
tags:
  - tag1
  - tag2
slug: post-{i}
---
# Content for post {i}
""" + "bla " * 1000
        (posts_dir / f"post-{i}.md").write_text(content, encoding="utf-8")

    return tmp_path

@pytest.fixture
def huge_file_dir(tmp_path):
    """Create a mock site directory with 1 huge post (5MB)."""
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()

    # Create 1 huge post (5MB)
    content = f"""---
title: Huge Post
date: 2024-01-01
slug: huge
---
""" + "A" * (5 * 1024 * 1024)
    (posts_dir / "huge.md").write_text(content, encoding="utf-8")
    return tmp_path

def test_site_generator_scan_benchmark(large_site_dir, benchmark):
    """Benchmark for full scan (baseline).

    This loads all content into memory (Document objects).
    """
    site_root = large_site_dir
    generator = SiteGenerator(
        site_root=site_root,
        docs_dir=site_root,
        posts_dir=site_root / "posts",
        profiles_dir=site_root / "profiles",
        media_dir=site_root / "media",
        journal_dir=site_root / "journal",
        url_convention=MockUrlConvention(),
        url_context=MockUrlContext(),
    )

    def scan():
        # Force iteration to consume the generator
        return list(generator._scan_directory(generator.posts_dir, DocumentType.POST))

    benchmark(scan)

def test_get_site_stats_benchmark(large_site_dir, benchmark):
    """Benchmark for get_site_stats.

    Should be much faster than scan as it shouldn't read file content.
    """
    site_root = large_site_dir
    # Create other dirs
    (site_root / "profiles").mkdir()
    (site_root / "media").mkdir()
    (site_root / "media" / "urls").mkdir()
    (site_root / "journal").mkdir()

    generator = SiteGenerator(
        site_root=site_root,
        docs_dir=site_root,
        posts_dir=site_root / "posts",
        profiles_dir=site_root / "profiles",
        media_dir=site_root / "media",
        journal_dir=site_root / "journal",
        url_convention=MockUrlConvention(),
        url_context=MockUrlContext(),
    )

    benchmark(generator.get_site_stats)

def test_regenerate_tags_page_benchmark(large_site_dir, benchmark):
    """Benchmark for regenerate_tags_page.

    Should be efficient by reading only metadata.
    """
    site_root = large_site_dir

    generator = SiteGenerator(
        site_root=site_root,
        docs_dir=site_root,
        posts_dir=site_root / "posts",
        profiles_dir=site_root / "profiles",
        media_dir=site_root / "media",
        journal_dir=site_root / "journal",
        url_convention=MockUrlConvention(),
        url_context=MockUrlContext(),
    )
    # Mock template env to avoid jinja errors
    mock_template = MagicMock()
    mock_template.render.return_value = "content"
    generator._template_env = MagicMock()
    generator._template_env.get_template.return_value = mock_template

    benchmark(generator.regenerate_tags_page)

def test_huge_file_read_metadata_benchmark(huge_file_dir, benchmark):
    """Benchmark for _read_metadata on large file.

    Demonstrates O(1) vs O(N) advantage over full load.
    """
    post_path = huge_file_dir / "posts" / "huge.md"
    benchmark(SiteGenerator._read_metadata, post_path)
