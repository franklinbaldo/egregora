from __future__ import annotations

from pathlib import Path

import yaml

from egregora.utils.filesystem import sync_authors_from_posts


def test_sync_authors_from_posts(tmp_path: Path):
    # 1. Arrange
    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts" / "posts"
    posts_dir.mkdir(parents=True)

    # Create mock posts
    post1_content = """---
authors:
  - frodo
  - sam
---
A hobbit's tale.
"""
    (posts_dir / "post1.md").write_text(post1_content, "utf-8")

    post2_content = """---
authors: bilbo
---
There and back again.
"""
    (posts_dir / "post2.md").write_text(post2_content, "utf-8")

    post3_content = """---
# No authors here
---
Just a story.
"""
    (posts_dir / "post3.md").write_text(post3_content, "utf-8")

    # Pre-existing authors file
    authors_yml_path = docs_dir / ".authors.yml"
    existing_authors = {
        "gandalf": {
            "name": "gandalf",
            "url": "profiles/gandalf.md",
        }
    }
    authors_yml_path.write_text(yaml.dump(existing_authors), "utf-8")

    # 2. Act
    new_authors_count = sync_authors_from_posts(posts_dir, docs_dir)

    # 3. Assert
    assert new_authors_count == 3  # frodo, sam, bilbo

    final_authors = yaml.safe_load(authors_yml_path.read_text("utf-8"))
    assert "frodo" in final_authors
    assert "sam" in final_authors
    assert "bilbo" in final_authors
    assert "gandalf" in final_authors  # Existing author preserved
    assert final_authors["sam"]["name"] == "sam"
    assert final_authors["bilbo"]["url"] == "profiles/bilbo.md"
    assert len(final_authors) == 4
