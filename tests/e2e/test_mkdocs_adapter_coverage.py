"""Test coverage for MkDocsAdapter."""

import pytest

from egregora.data_primitives.document import Document, DocumentType
from egregora.output_adapters.mkdocs import MkDocsAdapter


@pytest.fixture
def adapter(tmp_path):
    """Fixture to create and initialize an MkDocsAdapter."""
    adapter = MkDocsAdapter()
    adapter.initialize(tmp_path)
    return adapter


def test_write_profile_doc_generates_fallback_avatar(adapter):
    """Test that writing a profile without an avatar generates a fallback one.

    This also verifies that 'generate_fallback_avatar_url' is correctly imported and used,
    preventing the 'Critical Bug' where the private version was imported.
    """

    # Create a profile document without avatar in metadata
    author_uuid = "test-uuid-123"
    doc = Document(
        content="# Bio\nUser bio.",
        type=DocumentType.PROFILE,
        metadata={"uuid": author_uuid, "subject": author_uuid, "slug": "bio", "name": "Test User"},
    )

    # Persist
    adapter.persist(doc)

    # Check file content
    profile_path = adapter.profiles_dir / author_uuid / "bio.md"
    assert profile_path.exists()
    content = profile_path.read_text(encoding="utf-8")

    # Verify avatar in frontmatter (fallback URL from avataaars.io)
    # Check for prefix to be robust
    assert "avatar: https://avataaars.io/?" in content

    # Verify avatar image in content (MkDocs macro)
    # The adapter prepends the avatar macro to the content
    assert "![Avatar]({{ page.meta.avatar }}){ align=left width=150 }" in content


def test_write_post_doc_adds_related_posts(adapter):
    """Test that writing a post adds related posts based on tags."""

    # Create two posts with shared tags
    post1 = Document(
        content="# Post 1",
        type=DocumentType.POST,
        metadata={"title": "Post 1", "date": "2024-01-01", "slug": "post-1", "tags": ["tag1", "tag2"]},
    )
    post2 = Document(
        content="# Post 2",
        type=DocumentType.POST,
        metadata={"title": "Post 2", "date": "2024-01-02", "slug": "post-2", "tags": ["tag2", "tag3"]},
    )

    # Persist post1 first
    adapter.persist(post1)

    # Persist post2
    adapter.persist(post2)

    # Re-persist post1 so it can find post2 as related (since post2 is now in index/disk)
    # Note: MkDocsAdapter.persist uses self.documents() which reads from disk.
    # We need to make sure post2 is flushed/available. self.documents() iterates over files.

    # Force re-write of post1
    adapter.persist(post1)

    # Check post1 content
    post1_path = adapter.posts_dir / "2024-01-01-post-1.md"
    content = post1_path.read_text(encoding="utf-8")

    # Verify related_posts in frontmatter
    # related_posts should contain post2 because they share "tag2"
    assert "related_posts:" in content
    assert "title: Post 2" in content


def test_get_profiles_data_generates_stats(adapter):
    """Test get_profiles_data calculates stats correctly."""

    uuid = "user-stats"

    # Create profile
    profile = Document(
        content="Bio",
        type=DocumentType.PROFILE,
        metadata={"uuid": uuid, "subject": uuid, "slug": "bio", "name": "Stats User"},
    )
    adapter.persist(profile)

    # Create posts for this user
    # Note: author uuid in 'authors' list
    post = Document(
        content="word " * 10,  # 10 words
        type=DocumentType.POST,
        metadata={"title": "Post", "date": "2024-01-01", "slug": "p1", "authors": [uuid], "tags": ["topic1"]},
    )
    adapter.persist(post)

    # Get stats using the PUBLIC API
    profiles = adapter.get_profiles_data()

    assert len(profiles) == 1
    p = profiles[0]
    assert p["uuid"] == uuid
    assert p["post_count"] == 1
    assert p["word_count"] == 10
    assert "topic1" in p["topics"]
    assert p["topic_counts"][0] == ("topic1", 1)


def test_mkdocs_adapter_scaffolding_passthrough(adapter, tmp_path):
    """Test that scaffolding methods are passed through to the scaffolder."""

    # validate_structure checks for mkdocs.yml
    assert not adapter.validate_structure(tmp_path)

    # scaffold a site
    (tmp_path / "mkdocs.yml").touch()
    assert adapter.validate_structure(tmp_path)
