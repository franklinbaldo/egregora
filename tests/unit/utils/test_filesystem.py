from datetime import date, datetime
from pathlib import Path

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


def test_sync_authors_from_posts(tmp_path: Path):
    """Verify sync_authors_from_posts correctly finds authors from frontmatter."""
    # 1. Setup mock directory and files
    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts" / "posts"
    posts_dir.mkdir(parents=True)

    # Post with a list of authors
    (posts_dir / "post1.md").write_text(
        """---
authors: [author1, author2]
---
Content.
""",
        encoding="utf-8",
    )

    # Post with a single author string
    (posts_dir / "post2.md").write_text(
        """---
authors: author3
---
Content.
""",
        encoding="utf-8",
    )

    # Post with no authors field
    (posts_dir / "post3.md").write_text(
        """---
title: No authors
---
Content.
""",
        encoding="utf-8",
    )

    # Post with an empty author list
    (posts_dir / "post4.md").write_text(
        """---
authors: []
---
Content.
""",
        encoding="utf-8",
    )

    # Post with a null author
    (posts_dir / "post5.md").write_text(
        """---
authors: null
---
Content.
""",
        encoding="utf-8",
    )

    # 2. Run the function
    new_authors_count = sync_authors_from_posts(posts_dir, docs_dir)

    # 3. Assertions
    assert new_authors_count == 3
    authors_yml_path = docs_dir / ".authors.yml"
    assert authors_yml_path.exists()

    with open(authors_yml_path, "r", encoding="utf-8") as f:
        authors_data = yaml.safe_load(f)

    assert "author1" in authors_data
    assert "author2" in authors_data
    assert "author3" in authors_data
    assert len(authors_data) == 3

    assert authors_data["author1"]["name"] == "author1"
    assert authors_data["author1"]["url"] == "profiles/author1.md"

    # Run again, should register no new authors
    new_authors_count_rerun = sync_authors_from_posts(posts_dir, docs_dir)
    assert new_authors_count_rerun == 0
