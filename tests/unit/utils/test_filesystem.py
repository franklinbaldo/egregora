from datetime import date, datetime
from pathlib import Path

import pytest
import yaml

from egregora.utils.filesystem import _extract_clean_date, sync_authors_from_posts


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


@pytest.fixture
def sample_posts(tmp_path: Path) -> Path:
    """Create a sample posts directory with various author frontmatter styles."""
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()

    # Case 1: Authors as a list
    post1_content = """---
authors:
  - frodo
  - sam
---
A fellowship is born.
"""
    (posts_dir / "post1.md").write_text(post1_content, "utf-8")

    # Case 2: Author as a single string
    post2_content = """---
authors: bilbo
---
There and back again.
"""
    (posts_dir / "post2.md").write_text(post2_content, "utf-8")

    # Case 3: No authors
    post3_content = """---
title: A Party of Special Magnificence
---
No authors here.
"""
    (posts_dir / "post3.md").write_text(post3_content, "utf-8")

    return posts_dir


def test_sync_authors_from_posts_handles_list_and_string(sample_posts: Path):
    """Verify sync_authors_from_posts handles both list and string author fields."""
    docs_dir = sample_posts.parent / "docs"
    docs_dir.mkdir()

    # Act
    new_author_count = sync_authors_from_posts(sample_posts, docs_dir=docs_dir)

    # Assert
    authors_yml_path = docs_dir / ".authors.yml"
    assert new_author_count == 3
    assert authors_yml_path.exists()

    with authors_yml_path.open("r", encoding="utf-8") as f:
        authors_data = yaml.safe_load(f)

    expected_data = {
        "frodo": {"name": "frodo", "url": "profiles/frodo.md"},
        "sam": {"name": "sam", "url": "profiles/sam.md"},
        "bilbo": {"name": "bilbo", "url": "profiles/bilbo.md"},
    }
    assert authors_data == expected_data
