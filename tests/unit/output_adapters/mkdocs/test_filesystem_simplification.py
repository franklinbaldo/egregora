from __future__ import annotations

import yaml
from pathlib import Path

from egregora.output_adapters.mkdocs.filesystem import sync_authors_from_posts


def test_sync_authors_from_posts_handles_various_formats(tmp_path: Path):
    """Verify sync_authors_from_posts correctly processes authors from mixed frontmatter formats."""
    # 1. Setup: Create mock post files and an initial .authors.yml
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()

    (tmp_path / ".authors.yml").write_text(
        yaml.dump({"author2": {"name": "author2", "url": "..."}}), encoding="utf-8"
    )

    # Post 1: Author list
    (posts_dir / "post1.md").write_text(
        """---
title: Post 1
authors: [author1, author2]
---
Content
""",
        encoding="utf-8",
    )

    # Post 2: Single author string
    (posts_dir / "post2.md").write_text(
        """---
title: Post 2
authors: author3
---
Content
""",
        encoding="utf-8",
    )

    # Post 3: Empty authors key
    (posts_dir / "post3.md").write_text(
        """---
title: Post 3
authors:
---
Content
""",
        encoding="utf-8",
    )

    # Post 4: No authors key
    (posts_dir / "post4.md").write_text(
        """---
title: Post 4
---
Content
""",
        encoding="utf-8",
    )

    # Post 5: Duplicate author to ensure set logic works
    (posts_dir / "post5.md").write_text(
        """---
title: Post 5
authors: [author1, author4]
---
Content
""",
        encoding="utf-8",
    )

    # 2. Action: Run the function
    new_authors_count = sync_authors_from_posts(posts_dir=posts_dir, docs_dir=tmp_path)

    # 3. Verification
    assert new_authors_count == 3  # author1, author3, author4 are new

    with (tmp_path / ".authors.yml").open("r", encoding="utf-8") as f:
        final_authors = yaml.safe_load(f)

    assert "author1" in final_authors
    assert "author2" in final_authors  # Was pre-existing
    assert "author3" in final_authors
    assert "author4" in final_authors
    assert len(final_authors) == 4
    assert final_authors["author1"]["name"] == "author1"
