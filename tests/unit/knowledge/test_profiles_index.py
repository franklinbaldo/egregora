from pathlib import Path

import yaml

from egregora.knowledge.profiles import ensure_author_profile_index


def test_ensure_author_profile_index_creates_index_and_authors(tmp_path: Path) -> None:
    profiles_dir = tmp_path / "docs" / "posts" / "profiles"
    author_uuid = "test-author-uuid"
    author_dir = profiles_dir / author_uuid
    author_dir.mkdir(parents=True)

    post_path = author_dir / "2025-01-01-interest-update-test-author.md"
    post_path.write_text(
        """---
title: Interest Update
date: 2025-01-01
slug: 2025-01-01-interest-update-test-author
---

# Profile Update

This is a test profile post.
""",
        encoding="utf-8",
    )

    index_path = ensure_author_profile_index(author_uuid, profiles_dir)
    assert index_path.exists()

    index_content = index_path.read_text(encoding="utf-8")
    assert "Profile Posts" in index_content
    assert "- [Interest Update](2025-01-01-interest-update-test-author.md) — 2025-01-01" in index_content

    authors_yml_path = profiles_dir.parent / ".authors.yml"
    assert authors_yml_path.exists()
    authors = yaml.safe_load(authors_yml_path.read_text(encoding="utf-8"))
    assert author_uuid in authors
    assert authors[author_uuid]["url"] == f"profiles/{author_uuid}/"
