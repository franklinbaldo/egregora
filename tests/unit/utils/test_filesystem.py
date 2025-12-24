from datetime import date, datetime
from pathlib import Path
import yaml

from egregora.utils.filesystem import _extract_clean_date, sync_authors_from_posts


def test_sync_authors_from_posts(tmp_path: Path):
    # 1. Setup the file structure
    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts" / "posts"
    posts_dir.mkdir(parents=True)

    authors_yml_path = docs_dir / ".authors.yml"
    # Start with one existing author
    initial_authors = {"existing_author": {"name": "Existing Author"}}
    authors_yml_path.write_text(yaml.dump(initial_authors))

    # 2. Create mock posts
    # Post with a single author string
    post1_content = """---
authors: single_author
---
Content here.
"""
    (posts_dir / "post1.md").write_text(post1_content)

    # Post with a list of authors, including one already present
    post2_content = """---
authors:
  - list_author_1
  - existing_author
  - list_author_2
---
Content here.
"""
    (posts_dir / "post2.md").write_text(post2_content)

    # Post with no authors
    post3_content = """---
title: No authors here
---
Content here.
"""
    (posts_dir / "post3.md").write_text(post3_content)


    # 3. Run the function
    new_authors_count = sync_authors_from_posts(posts_dir)

    # 4. Assert the results
    assert new_authors_count == 3  # single_author, list_author_1, list_author_2

    final_authors = yaml.safe_load(authors_yml_path.read_text())

    assert "existing_author" in final_authors
    assert "single_author" in final_authors
    assert "list_author_1" in final_authors
    assert "list_author_2" in final_authors

    assert final_authors["single_author"]["name"] == "single_author"
    assert final_authors["list_author_1"]["url"] == "profiles/list_author_1.md"


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
