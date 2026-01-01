# tests/unit/utils/test_authors_performance.py
import pytest
import yaml

from egregora.utils.authors import sync_authors_from_posts

# Number of files to generate for the performance test.
# A higher number provides a more realistic workload for I/O-bound tasks.
NUM_FILES = 500


@pytest.fixture
def author_posts(tmp_path):
    """Fixture to create a realistic directory of posts with author frontmatter."""
    posts_dir = tmp_path / "docs" / "posts"
    posts_dir.mkdir(parents=True)

    # Generate a large number of markdown files
    for i in range(NUM_FILES):
        author_id = f"author_{i % 50}"  # Cycle through 50 unique authors
        content = f"""---
title: "Post {i}"
authors:
  - {author_id}
---

This is post number {i}.
"""
        (posts_dir / f"post_{i}.md").write_text(content, encoding="utf-8")
    return posts_dir


def test_sync_authors_from_posts_benchmark(benchmark, author_posts):
    """
    Benchmark the performance of sync_authors_from_posts.
    This test establishes a baseline for the I/O-heavy operation of scanning
    and parsing numerous markdown files.
    """
    docs_dir = author_posts.parent
    authors_file = docs_dir / ".authors.yml"

    def run_sync_with_cleanup():
        """Wrapper to ensure the .authors.yml file is removed before each benchmark run."""
        if authors_file.exists():
            authors_file.unlink()
        return sync_authors_from_posts(author_posts, docs_dir)

    # Benchmark the wrapped function to ensure a clean state for each run.
    result = benchmark(run_sync_with_cleanup)

    # Correctness check: ensure it found the correct number of unique authors.
    assert result == 50

    # Further correctness check: verify the content of the generated .authors.yml
    assert authors_file.exists()

    with authors_file.open(encoding="utf-8") as f:
        authors_data = yaml.safe_load(f)

    assert len(authors_data) == 50
    assert "author_0" in authors_data
    assert "author_49" in authors_data
