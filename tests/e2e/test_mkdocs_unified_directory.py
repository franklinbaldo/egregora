"""E2E tests for MkDocsAdapter path conventions (ADRs 0001/0002/0004).

These tests validate that the MkDocs adapter persists and discovers documents using
the posts-centric directory layout:

- Posts:            docs/posts/{date}-{slug}.md
- Profiles:         docs/posts/profiles/{author_uuid}/{slug}.md
- URL enrichments:  docs/posts/media/urls/{slug}.md
"""

from __future__ import annotations

import pytest
from egregora.output_sinks.mkdocs import MkDocsAdapter

from egregora.data_primitives.document import Document, DocumentType


@pytest.fixture
def adapter(tmp_path):
    output = MkDocsAdapter()
    output.initialize(tmp_path)
    return output


def test_post_persists_to_posts_dir(adapter):
    post = Document(
        content="# Test Post",
        type=DocumentType.POST,
        metadata={"title": "Test Post", "date": "2024-01-01", "slug": "test-post", "tags": ["test"]},
    )
    adapter.persist(post)
    assert (adapter.posts_dir / "2024-01-01-test-post.md").exists()


def test_profile_persists_to_profiles_subdir(adapter):
    author_uuid = "user-123"
    profile = Document(
        content="# Profile",
        type=DocumentType.PROFILE,
        metadata={"uuid": author_uuid, "subject": author_uuid, "slug": "bio", "name": "Test User"},
    )
    adapter.persist(profile)
    assert (adapter.profiles_dir / author_uuid / "bio.md").exists()


def test_url_enrichment_persists_to_media_urls(adapter):
    enrichment = Document(
        content="# Enriched Content",
        type=DocumentType.ENRICHMENT_URL,
        metadata={"slug": "enriched-url", "url": "https://example.com"},
    )
    adapter.persist(enrichment)
    matches = list((adapter.media_dir / "urls").glob("enriched-url-*.md"))
    assert matches


def test_list_finds_posts_profiles_and_enrichments(adapter):
    author_uuid = "profile-type-test"
    adapter.persist(
        Document(
            content="# Post",
            type=DocumentType.POST,
            metadata={"title": "Post", "date": "2024-01-01", "slug": "post-type-test", "tags": ["test"]},
        )
    )
    adapter.persist(
        Document(
            content="# Profile",
            type=DocumentType.PROFILE,
            metadata={"uuid": author_uuid, "subject": author_uuid, "slug": "bio", "name": "Test User"},
        )
    )
    adapter.persist(
        Document(
            content="# Enrichment",
            type=DocumentType.ENRICHMENT_URL,
            metadata={"slug": "enrich-type-test", "url": "https://example.com"},
        )
    )

    all_docs = list(adapter.list())
    types = {meta.doc_type for meta in all_docs}
    assert DocumentType.POST in types
    assert DocumentType.PROFILE in types
    assert DocumentType.ENRICHMENT_URL in types

    enrichments = list(adapter.list(doc_type=DocumentType.ENRICHMENT_URL))
    assert len(enrichments) == 1
