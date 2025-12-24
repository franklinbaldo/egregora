import textwrap
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml

from egregora.utils.filesystem import _extract_clean_date, sync_authors_from_posts


@pytest.fixture
def site_structure(tmp_path: Path) -> Path:
    """Creates a temporary site structure for testing."""
    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts" / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)
    return docs_dir


def create_post(path: Path, frontmatter: dict):
    """Helper to create a markdown file with frontmatter."""
    content = f"---\n{yaml.dump(frontmatter)}---\n\nHello World."
    path.write_text(textwrap.dedent(content))


def test_sync_authors_from_posts(site_structure: Path):
    """Verify sync_authors_from_posts correctly finds and registers authors."""
    docs_dir = site_structure
    posts_dir = docs_dir / "posts" / "posts"
    authors_path = docs_dir / ".authors.yml"

    # 1. Setup initial state
    # An existing authors file
    initial_authors = {"existing_author": {"name": "Existing Author"}}
    authors_path.write_text(yaml.dump(initial_authors))

    # Create posts with various author formats
    create_post(
        posts_dir / "post1.md",
        {"title": "Post 1", "authors": ["author_one", "author_two"]},
    )
    create_post(
        posts_dir / "post2.md",
        {"title": "Post 2", "authors": "author_three"},
    )
    create_post(
        posts_dir / "post3.md",
        {"title": "Post 3", "authors": ["author_one", "existing_author"]},
    )
    create_post(posts_dir / "post4.md", {"title": "Post 4"})  # No authors
    create_post(
        posts_dir / "post5.md", {"title": "Post 5", "authors": None}
    )  # Null authors

    # 2. Run the function
    new_authors_count = sync_authors_from_posts(posts_dir)

    # 3. Assert the results
    assert new_authors_count == 3
    assert authors_path.exists()

    final_authors = yaml.safe_load(authors_path.read_text())
    expected_authors = {
        "existing_author": {"name": "Existing Author"},
        "author_one": {"name": "author_one", "url": "profiles/author_one.md"},
        "author_two": {"name": "author_two", "url": "profiles/author_two.md"},
        "author_three": {"name": "author_three", "url": "profiles/author_three.md"},
    }

    assert final_authors == expected_authors


def test_extract_clean_date_str():
    assert _extract_clean_date("2023-01-01") == "2023-01-01"
    assert _extract_clean_date("2023-01-01T12:00:00") == "2023-01-01"
    assert _extract_clean_date("  2023-01-01  ") == "2023-01-01"
    assert _extract_clean_date("Some text 2023-01-01 inside") == "2023-01-01"


def test_extract_clean_date_objects():
    d = date(2023, 1, 1)
    dt = datetime(2023, 1, 1, 12, 0, 0)
    assert _extract_clean_date(d) == "2023-01-01"
    assert _extract_clean_date(dt) == "2023-01-01"


def test_extract_clean_date_invalid():
    # If no date found, returns original string
    assert _extract_clean_date("invalid") == "invalid"
    assert _extract_clean_date("") == ""
