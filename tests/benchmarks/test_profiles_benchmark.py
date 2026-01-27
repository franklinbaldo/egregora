import pytest
from pathlib import Path
from egregora.output_sinks.mkdocs.site_generator import SiteGenerator
from egregora.data_primitives.document import UrlContext
from egregora.output_sinks.conventions import StandardUrlConvention

@pytest.fixture
def site_gen_profiles(tmp_path):
    site_root = tmp_path / "site"
    docs_dir = site_root / "docs"
    posts_dir = docs_dir / "posts"
    profiles_dir = docs_dir / "profiles"
    media_dir = docs_dir / "media"
    journal_dir = docs_dir / "journal"

    for d in [posts_dir, profiles_dir, media_dir, journal_dir, media_dir / "urls"]:
        d.mkdir(parents=True, exist_ok=True)

    authors = [f"author_{i}" for i in range(10)]

    # Create authors
    for author in authors:
        d = profiles_dir / author
        d.mkdir()
        (d / "profile.md").write_text(f"""---
name: Name {author}
---
Bio
""")

    # Create 200 posts, assigning to authors round-robin
    # Content length ~5KB
    content = "word " * 1000
    for i in range(200):
        author = authors[i % len(authors)]
        (posts_dir / f"post_{i}.md").write_text(f"""---
title: Post {i}
date: 2024-01-01
slug: post-{i}
tags: [tag1, tag2]
authors: [{author}]
---
# Content for post {i}
{content}
""")

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

def test_get_profiles_data_benchmark(benchmark, site_gen_profiles):
    benchmark(site_gen_profiles.get_profiles_data)
