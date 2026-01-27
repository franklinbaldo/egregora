import pytest

from egregora.data_primitives.document import UrlContext
from egregora.output_sinks.conventions import StandardUrlConvention
from egregora.output_sinks.mkdocs.site_generator import SiteGenerator


@pytest.fixture
def site_gen(tmp_path):
    site_root = tmp_path / "site"
    docs_dir = site_root / "docs"
    posts_dir = docs_dir / "posts"
    profiles_dir = docs_dir / "profiles"
    media_dir = docs_dir / "media"
    journal_dir = docs_dir / "journal"

    for d in [posts_dir, profiles_dir, media_dir, journal_dir, media_dir / "urls"]:
        d.mkdir(parents=True, exist_ok=True)

    # Create 100 posts with 50KB content (representative size)
    # The optimization benefits scale linearly with size, so for larger files
    # the improvement is even more dramatic.
    for i in range(100):
        (posts_dir / f"post_{i}.md").write_text(
            f"""---
title: Post {i}
date: 2024-01-01
slug: post-{i}
tags: [tag1, tag2]
banner: image.png
---
# Content for post {i}
"""
            + "blah " * 10000
        )

    return SiteGenerator(
        site_root=site_root,
        docs_dir=docs_dir,
        posts_dir=posts_dir,
        profiles_dir=profiles_dir,
        media_dir=media_dir,
        journal_dir=journal_dir,
        url_convention=StandardUrlConvention(),
        url_context=UrlContext(base_url="http://localhost"),
    )


def test_get_site_stats_benchmark(benchmark, site_gen):
    benchmark(site_gen.get_site_stats)


def test_get_recent_posts_benchmark(benchmark, site_gen):
    benchmark(site_gen.get_recent_posts, limit=10)
