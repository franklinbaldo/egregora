"""Tests for author-related filesystem utilities."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Any

import frontmatter
import pytest
import yaml

from egregora.knowledge.profiles import (
    ensure_author_entries,
    find_authors_yml,
    sync_authors_from_posts,
)

if TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture


NUM_FILES = 500


def create_post(path: Path, frontmatter_dict: dict[str, Any]) -> None:
    """Helper to create a markdown file with YAML frontmatter."""
    content = f"---\n{yaml.dump(frontmatter_dict)}---\n\nHello World."
    path.write_text(dedent(content), encoding="utf-8")


@pytest.fixture
def project_structure(tmp_path: Path) -> tuple[Path, Path]:
    """Creates a standard docs/posts/posts project structure."""
    posts_dir = tmp_path / "docs" / "posts" / "posts"
    posts_dir.mkdir(parents=True)
    docs_dir = tmp_path / "docs"
    return docs_dir, posts_dir


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


def _create_post(path: Path, authors: list[str] | None = None) -> None:
    """Helper to create a markdown file with authors in frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(content=f"Content for {path.stem}", authors=authors or [])
    path.write_text(frontmatter.dumps(post), encoding="utf-8")


def test_sync_authors_from_posts_standard_layout(tmp_path: Path) -> None:
    """Verify it syncs authors in a standard `docs/posts` layout."""
    # Arrange
    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    authors_path = docs_dir / ".authors.yml"
    _create_post(posts_dir / "post1.md", authors=["author-one"])
    _create_post(posts_dir / "post2.md", authors=["author-two"])

    # Act
    new_count = sync_authors_from_posts(posts_dir)

    # Assert
    assert new_count == 2
    assert authors_path.exists()
    authors_data = yaml.safe_load(authors_path.read_text())
    assert "author-one" in authors_data
    assert "author-two" in authors_data


def test_sync_authors_from_posts_fallback_layout(tmp_path: Path) -> None:
    """Verify it syncs authors using the fallback path resolution."""
    # Arrange
    posts_dir = tmp_path / "output" / "posts"
    # The fallback path is output_dir.parent.parent / ".authors.yml"
    authors_path = tmp_path / ".authors.yml"
    _create_post(posts_dir / "post1.md", authors=["author-one"])

    # Act
    new_count = sync_authors_from_posts(posts_dir)

    # Assert
    assert new_count == 1
    assert authors_path.exists()
    authors_data = yaml.safe_load(authors_path.read_text())
    assert "author-one" in authors_data


def test_sync_authors_from_posts_no_authors(tmp_path: Path) -> None:
    """Verify it does nothing if posts have no authors."""
    # Arrange
    posts_dir = tmp_path / "docs" / "posts"
    authors_path = tmp_path / "docs" / ".authors.yml"
    _create_post(posts_dir / "post1.md", authors=None)

    # Act
    new_count = sync_authors_from_posts(posts_dir)

    # Assert
    assert new_count == 0
    assert not authors_path.exists()


def test_find_authors_yml_standard_layout(tmp_path: Path) -> None:
    """Verify it finds .authors.yml in a standard docs layout."""
    # Arrange
    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    posts_dir.mkdir(parents=True)
    expected_path = docs_dir / ".authors.yml"
    expected_path.touch()

    # Act
    result = find_authors_yml(posts_dir)

    # Assert
    assert result == expected_path


def test_find_authors_yml_nested_layout(tmp_path: Path) -> None:
    """Verify it finds .authors.yml from a deeper path."""
    # Arrange
    docs_dir = tmp_path / "site" / "docs"
    deep_dir = docs_dir / "section" / "posts"
    deep_dir.mkdir(parents=True)
    expected_path = docs_dir / ".authors.yml"
    expected_path.touch()

    # Act
    result = find_authors_yml(deep_dir)

    # Assert
    assert result == expected_path


def test_find_authors_yml_fallback_behavior(tmp_path: Path) -> None:
    """Verify it falls back to the legacy path if 'docs' is not found."""
    # Arrange
    output_dir = tmp_path / "output" / "posts"
    output_dir.mkdir(parents=True)
    # Fallback path is output_dir.parent.parent / ".authors.yml"
    expected_path = tmp_path / ".authors.yml"
    expected_path.touch()

    # Act
    result = find_authors_yml(output_dir)

    # Assert
    assert result == expected_path


def test_sync_authors_from_posts(tmp_path: Path):
    """Verify that `sync_authors_from_posts` correctly finds and registers new authors."""
    # 1. Setup the test environment
    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts" / "posts"
    posts_dir.mkdir(parents=True)

    # Create an initial .authors.yml with one existing author
    authors_path = docs_dir / ".authors.yml"
    initial_authors = {
        "existing_author": {
            "name": "Existing Author",
            "url": "profiles/existing_author.md",
        }
    }
    authors_path.write_text(yaml.dump(initial_authors), encoding="utf-8")

    # Create mock post files
    # Post with a single new author (string)
    (posts_dir / "post1.md").write_text(
        """---
title: Post 1
authors: new_author_1
---
Content 1
""",
        encoding="utf-8",
    )

    # Post with a list of authors (one new, one existing)
    (posts_dir / "post2.md").write_text(
        """---
title: Post 2
authors:
  - new_author_2
  - existing_author
---
Content 2
""",
        encoding="utf-8",
    )

    # Post with no authors field
    (posts_dir / "post3.md").write_text(
        """---
title: Post 3
---
Content 3
""",
        encoding="utf-8",
    )

    # An invalid file that should be skipped
    (posts_dir / "not-a-post.txt").write_text("This is not a markdown file.")

    # 2. Run the function
    new_authors_count = sync_authors_from_posts(posts_dir)

    # 3. Assert the results
    assert new_authors_count == 2

    # Verify the .authors.yml file was updated correctly
    final_authors = yaml.safe_load(authors_path.read_text(encoding="utf-8"))
    assert "existing_author" in final_authors
    assert "new_author_1" in final_authors
    assert "new_author_2" in final_authors
    assert final_authors["new_author_1"]["name"] == "new_author_1"
    assert final_authors["new_author_2"]["url"] == "profiles/new_author_2.md"
    assert len(final_authors) == 3


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


def test_sync_authors_from_posts_with_new_authors(project_structure: tuple[Path, Path]) -> None:
    """Verify new authors from posts are added to .authors.yml."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    authors_yml.write_text(yaml.dump({"existing_author": {"name": "Existing"}}), "utf-8")

    create_post(posts_dir / "post1.md", {"authors": ["new_author_1"]})
    create_post(posts_dir / "post2.md", {"authors": ["new_author_2", "existing_author"]})

    new_authors_count = sync_authors_from_posts(posts_dir)

    assert new_authors_count == 2
    with authors_yml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        assert "new_author_1" in data
        assert "new_author_2" in data
        assert data["new_author_1"]["name"] == "new_author_1"
        assert data["new_author_2"]["url"] == "profiles/new_author_2.md"
        assert "existing_author" in data


def test_sync_authors_from_posts_no_new_authors(project_structure: tuple[Path, Path]) -> None:
    """Verify it returns 0 and makes no changes if no new authors are found."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    initial_content = yaml.dump({"author1": {"name": "Author One"}})
    authors_yml.write_text(initial_content, "utf-8")

    create_post(posts_dir / "post1.md", {"authors": ["author1"]})

    new_authors_count = sync_authors_from_posts(posts_dir)

    assert new_authors_count == 0
    assert authors_yml.read_text("utf-8") == initial_content


def test_sync_authors_from_posts_no_authors_yml(project_structure: tuple[Path, Path]) -> None:
    """Verify it creates .authors.yml if it doesn't exist."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"

    create_post(posts_dir / "post1.md", {"authors": ["author1", "author2"]})

    new_authors_count = sync_authors_from_posts(posts_dir)

    assert new_authors_count == 2
    assert authors_yml.exists()
    with authors_yml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        assert "author1" in data


def test_ensure_author_entries_adds_new_authors(project_structure: tuple[Path, Path]) -> None:
    """Verify ensure_author_entries adds new authors and preserves existing ones."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    authors_yml.write_text(yaml.dump({"existing_author": {"name": "Existing"}}), "utf-8")

    # The 'output_dir' argument is the posts_dir
    ensure_author_entries(posts_dir, ["new_author_1", "existing_author", "new_author_2"])

    with authors_yml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        assert "new_author_1" in data
        assert "new_author_2" in data
        assert data["new_author_1"]["name"] == "new_author_1"
        assert "existing_author" in data
        assert len(data) == 3


def test_ensure_author_entries_creates_file(project_structure: tuple[Path, Path]) -> None:
    """Verify ensure_author_entries creates .authors.yml if it doesn't exist."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    assert not authors_yml.exists()

    ensure_author_entries(posts_dir, ["author1"])

    assert authors_yml.exists()
    with authors_yml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        assert "author1" in data


def test_ensure_author_entries_with_no_authors(
    project_structure: tuple[Path, Path], caplog: LogCaptureFixture
) -> None:
    """Verify it does nothing if the author list is empty or None."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    initial_content = yaml.dump({"existing": {"name": "Test"}})
    authors_yml.write_text(initial_content, "utf-8")

    # Test with empty list
    ensure_author_entries(posts_dir, [])
    assert authors_yml.read_text("utf-8") == initial_content
    assert "Registered 0 new author(s)" not in caplog.text

    # Test with None
    ensure_author_entries(posts_dir, None)
    assert authors_yml.read_text("utf-8") == initial_content
    assert "Registered 0 new author(s)" not in caplog.text


def test_sync_authors_from_posts_single_author_string(project_structure: tuple[Path, Path]) -> None:
    """Verify it correctly handles 'authors' as a single string, not a list."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    authors_yml.touch()

    create_post(posts_dir / "post1.md", {"authors": "string_author"})

    new_authors_count = sync_authors_from_posts(posts_dir)

    assert new_authors_count == 1
    with authors_yml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        assert "string_author" in data


def test_sync_authors_from_posts_no_author_metadata(
    project_structure: tuple[Path, Path], caplog: LogCaptureFixture
) -> None:
    """Verify it handles posts with no 'authors' key gracefully."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    authors_yml.touch()

    create_post(posts_dir / "post1.md", {"title": "A post with no author"})

    new_authors_count = sync_authors_from_posts(posts_dir)

    assert new_authors_count == 0
    assert "Synced 0 new author(s)" not in caplog.text


def test_sync_authors_from_posts_empty_authors_yml(project_structure: tuple[Path, Path]) -> None:
    """Verify it works correctly when .authors.yml is completely empty."""
    docs_dir, posts_dir = project_structure
    authors_yml = docs_dir / ".authors.yml"
    authors_yml.write_text("", "utf-8")

    create_post(posts_dir / "post1.md", {"authors": ["author1"]})

    new_authors_count = sync_authors_from_posts(posts_dir)

    assert new_authors_count == 1
    with authors_yml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        assert "author1" in data
