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


# Content for post1.md (existing author)
POST_1_CONTENT = """---
title: Post 1
authors:
  - existing_author
---

Content for post 1.
"""

# Content for post2.md (new author)
POST_2_CONTENT = """---
title: Post 2
authors:
  - new_author_1
---

Content for post 2.
"""

# Content for post3.md (multiple authors, one new)
POST_3_CONTENT = """---
title: Post 3
authors:
  - existing_author
  - new_author_2
---

Content for post 3.
"""

# Content for post4.md (no authors)
POST_4_CONTENT = """---
title: Post 4
---

Content for post 4.
"""

# Initial .authors.yml content
INITIAL_AUTHORS_CONTENT = """
existing_author:
  name: Existing Author
  url: profiles/existing_author.md
"""


def test_sync_authors_from_posts(tmp_path: Path):
    """Verify sync_authors_from_posts correctly finds and adds new authors."""
    # 1. Setup the directory structure and files
    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts" / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)

    authors_path = docs_dir / ".authors.yml"
    authors_path.write_text(INITIAL_AUTHORS_CONTENT)

    (posts_dir / "post1.md").write_text(POST_1_CONTENT)
    (posts_dir / "post2.md").write_text(POST_2_CONTENT)
    (posts_dir / "post3.md").write_text(POST_3_CONTENT)
    (posts_dir / "post4.md").write_text(POST_4_CONTENT)

    # 2. Call the function under test
    new_authors_count = sync_authors_from_posts(posts_dir)

    # 3. Assert the results
    assert new_authors_count == 2

    # Verify the content of .authors.yml
    updated_authors = yaml.safe_load(authors_path.read_text())
    assert "existing_author" in updated_authors
    assert "new_author_1" in updated_authors
    assert "new_author_2" in updated_authors
    assert updated_authors["new_author_1"]["name"] == "new_author_1"
    assert updated_authors["new_author_2"]["url"] == "profiles/new_author_2.md"
    assert len(updated_authors) == 3
