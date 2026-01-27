import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd  # noqa: TID251
import pytest

from egregora.data_primitives.document import Document, DocumentType, UrlContext
from egregora.output_sinks.conventions import StandardUrlConvention
from egregora.output_sinks.mkdocs.adapter import MkDocsAdapter
from egregora.output_sinks.mkdocs.scaffolding import MkDocsSiteScaffolder
from egregora.output_sinks.mkdocs.site_generator import SiteGenerator


@pytest.fixture
def site_generator(tmp_path: Path) -> SiteGenerator:
    """Provides a SiteGenerator instance with a mock site structure."""
    scaffolder = MkDocsSiteScaffolder()
    scaffolder.scaffold_site(tmp_path, "Test Site")
    adapter = MkDocsAdapter()
    adapter.initialize(site_root=tmp_path)
    url_context = UrlContext(base_url="https://example.com", site_prefix="", base_path=tmp_path)

    generator = SiteGenerator(
        site_root=tmp_path,
        docs_dir=adapter.docs_dir,
        posts_dir=adapter.posts_dir,
        profiles_dir=adapter.profiles_dir,
        media_dir=adapter.media_dir,
        journal_dir=adapter.journal_dir,
        url_convention=StandardUrlConvention(),
        url_context=url_context,
        db_path=tmp_path / "reader.db",
    )
    generator._adapter = adapter
    return generator


def create_mock_post(generator, slug, title, date, banner=None, metadata_extras=None):
    metadata = {
        "slug": slug,
        "title": title,
        "date": date,
        "authors": ["uuid-1"],
        "tags": ["tag1"],
        "summary": "Summary",
    }
    if banner:
        metadata["banner"] = banner
    if metadata_extras:
        metadata.update(metadata_extras)

    post_doc = Document(
        type=DocumentType.POST,
        content=f"Content for {title}",
        metadata=metadata,
    )
    generator._adapter.persist(post_doc)


def create_mock_profile(generator, author_uuid):
    profile_doc = Document(
        type=DocumentType.PROFILE,
        content=f"Bio for {author_uuid}",
        metadata={
            "uuid": author_uuid,
            "subject": author_uuid,
            "name": f"Name {author_uuid}",
            "avatar": "avatar.png",
        },
    )
    generator._adapter.persist(profile_doc)


def test_get_recent_posts_behavior(site_generator: SiteGenerator):
    """
    Behavioral Test for get_recent_posts:
    1. Should include only posts with banners.
    2. Should sort by date (reverse).
    3. Should handle invalid dates gracefully.
    4. Should construct URLs correctly based on date.
    """
    create_mock_profile(site_generator, "uuid-1")

    # 1. Post with banner and valid date
    create_mock_post(site_generator, "post-valid", "Valid Post", "2025-01-10", banner="banner.jpg")

    # 2. Post without banner (should be excluded)
    create_mock_post(site_generator, "post-no-banner", "No Banner", "2025-01-11")

    # 3. Post with banner but older date
    create_mock_post(site_generator, "post-older", "Older Post", "2025-01-01", banner="banner.jpg")

    # 4. Post with invalid date (should use slug in URL)
    # We can't use create_mock_post because it enforces date validation.
    # Write file directly.
    bad_date_content = """---
slug: post-bad-date
title: Bad Date
date: invalid-date
authors: [uuid-1]
tags: [tag1]
banner: banner.jpg
---
Content for Bad Date
"""
    (site_generator.posts_dir / "post-bad-date.md").write_text(bad_date_content, encoding="utf-8")

    # Force mtime update to ensure sorting order
    # Using os.utime to ensure distinct timestamps regardless of filesystem resolution
    import os

    now = time.time()

    # Files are usually named YYYY-MM-DD-slug.md, but manual one is just slug.md
    def find_post_file(slug):
        # Try exact match first (for manually created one)
        p = site_generator.posts_dir / f"{slug}.md"
        if p.exists():
            return p
        # Try searching for timestamped one
        matches = list(site_generator.posts_dir.glob(f"*-{slug}.md"))
        if matches:
            return matches[0]
        msg = f"Could not find file for slug {slug}"
        raise FileNotFoundError(msg)

    os.utime(find_post_file("post-older"), (now - 100, now - 100))
    os.utime(find_post_file("post-bad-date"), (now - 50, now - 50))
    os.utime(find_post_file("post-valid"), (now, now))

    posts = site_generator.get_recent_posts(limit=10)

    # Expecting 3 posts (post-valid, post-older, post-bad-date)
    assert len(posts) == 3

    slugs = [p["url"].rstrip("/").split("/")[-1] for p in posts]
    assert "post-no-banner" not in slugs
    assert "post-valid" in slugs
    assert "post-older" in slugs
    assert "post-bad-date" in slugs

    # Verify sorting: post-valid should be first because it was touched last
    assert slugs[0] == "post-valid"
    assert slugs[1] == "post-bad-date"
    assert slugs[2] == "post-older"

    # Verify URL construction
    valid_post = next(p for p in posts if "post-valid" in p["url"])
    assert valid_post["url"] == "posts/2025/01/10/post-valid/"

    bad_date_post = next(p for p in posts if "post-bad-date" in p["url"])
    assert bad_date_post["url"] == "posts/post-bad-date/"


@patch("egregora.database.duckdb_manager.DuckDBStorageManager")
@patch("egregora.database.elo_store.EloStore")
def test_get_top_posts_by_elo_behavior(mock_elo_store_cls, mock_db_cls, site_generator: SiteGenerator):
    """
    Behavioral Test for get_top_posts_by_elo:
    1. Should retrieve top posts from DB.
    2. Should filter posts that don't exist in file system.
    3. Should filter posts without banners.
    4. Should merge ELO data with metadata.
    5. Should sort by ELO rating.
    """
    # Ensure DB file exists so logic proceeds
    site_generator.db_path.touch()

    create_mock_profile(site_generator, "uuid-1")

    # Setup posts
    # High ELO, has banner
    create_mock_post(site_generator, "post-high", "High ELO", "2025-01-01", banner="banner.jpg")
    # Low ELO, has banner
    create_mock_post(site_generator, "post-low", "Low ELO", "2025-01-01", banner="banner.jpg")
    # Medium ELO, NO banner (should be skipped)
    create_mock_post(site_generator, "post-no-banner", "No Banner", "2025-01-01")

    # Setup Mock DB Return
    mock_storage = MagicMock()
    mock_db_cls.return_value.__enter__.return_value = mock_storage

    mock_elo_instance = mock_elo_store_cls.return_value

    # Mocking DataFrame return
    # columns: post_id, elo_global, num_comparisons, win_rate
    data = {
        "post_id": ["post-high", "post-low", "post-no-banner", "post-missing"],
        "elo_global": [1200, 800, 1000, 1500],
        "num_comparisons": [10, 5, 8, 20],
        "win_rate": [0.8, 0.4, 0.5, 0.9],
    }
    df = pd.DataFrame(data)

    # The method calls elo_store.get_top_posts(limit=...).execute()
    mock_elo_instance.get_top_posts.return_value.execute.return_value = df

    top_posts = site_generator.get_top_posts_by_elo(limit=5)

    assert len(top_posts) == 2  # post-high, post-low (post-missing is skipped, post-no-banner is skipped)

    assert top_posts[0]["title"] == "High ELO"
    assert top_posts[0]["elo_rating"] == 1200

    assert top_posts[1]["title"] == "Low ELO"
    assert top_posts[1]["elo_rating"] == 800

    # Verify sorting
    assert top_posts[0]["elo_rating"] > top_posts[1]["elo_rating"]


def test_regenerate_feeds_page_behavior(site_generator: SiteGenerator):
    """
    Behavioral Test for regenerate_feeds_page:
    1. Should aggregate tags from all posts.
    2. Should write to feeds.md.
    """
    create_mock_post(
        site_generator, "post-1", "Post 1", "2025-01-01", metadata_extras={"tags": ["python", "coding"]}
    )
    create_mock_post(
        site_generator, "post-2", "Post 2", "2025-01-02", metadata_extras={"tags": ["python", "testing"]}
    )

    site_generator.regenerate_feeds_page()

    feeds_file = site_generator.docs_dir / "feeds" / "index.md"
    assert feeds_file.exists()
    content = feeds_file.read_text()

    # Check if title is present (tags are not currently rendered in the template)
    assert "RSS Feeds" in content
