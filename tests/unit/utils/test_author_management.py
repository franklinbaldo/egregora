from __future__ import annotations

from pathlib import Path

import yaml

from egregora.utils.authors import sync_authors_from_posts


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
    new_authors_count = sync_authors_from_posts(posts_dir, docs_dir)

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
