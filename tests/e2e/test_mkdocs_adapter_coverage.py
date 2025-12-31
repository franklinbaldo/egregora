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

    # Verify avatar is NOT prepended to content body (it's only in frontmatter for index page use)
    # Content should remain clean without avatar macro
    assert "![Avatar]" not in content


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


def test_regenerate_main_index_renders_posts(tmp_path):
    """Ensure homepage lists recent posts after regeneration."""

    site_root = tmp_path / "site"
    adapter = MkDocsAdapter()
    adapter.scaffold_site(site_root, site_name="Homepage Test")
    adapter.initialize(site_root)

    post = Document(
        content="First post body with insights.",
        type=DocumentType.POST,
        metadata={
            "title": "First Post",
            "date": "2024-01-02",
            "slug": "first-post",
            "summary": "Summary text for homepage card.",
        },
    )
    adapter.persist(post)

    adapter.regenerate_main_index()

    index_path = site_root / "docs" / "index.md"
    index_content = index_path.read_text(encoding="utf-8")

    assert "First Post" in index_content
    assert "posts/2024-01-02-first-post.md" in index_content
    assert "Summary text for homepage card." in index_content
