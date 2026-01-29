import logging
from unittest.mock import Mock, patch

import frontmatter
import pytest

from egregora.data_primitives.document import Document, DocumentType, UrlContext
from egregora.output_sinks.exceptions import (
    AdapterNotInitializedError,
    DocumentNotFoundError,
    FileWriteError,
    ProfileMetadataError,
)
from egregora.output_sinks.mkdocs.adapter import MkDocsAdapter


@pytest.fixture
def adapter(tmp_path):
    site_root = tmp_path / "site"
    site_root.mkdir()
    adapter = MkDocsAdapter()
    # Initialize with a base_url to match default convention expectations if needed
    # but StandardUrlConvention usually produces relative paths if base_url is empty?
    # Let's use a clean context.
    adapter.initialize(
        site_root=site_root, url_context=UrlContext(base_url="https://example.com", site_prefix="")
    )
    return adapter


def test_persist_journal_behavior(adapter):
    """Behavior: Journals are persisted to journal_dir with correct metadata."""
    doc = Document(
        content="Journal content",
        type=DocumentType.JOURNAL,
        metadata={"title": "My Journal", "slug": "my-journal"},
        id="journal-123",
    )

    # Journals are now routed to posts_dir with journal metadata
    with patch.object(
        adapter._url_convention, "canonical_url", return_value="https://example.com/journal/my-journal"
    ):
        adapter.persist(doc)

    expected_path = adapter.posts_dir / "my-journal.md"
    assert expected_path.exists()

    post = frontmatter.load(expected_path)
    assert post.content.strip() == "Journal content"
    assert post.metadata["type"] == "journal"
    assert "Journal" in post.metadata["categories"]
    assert post.metadata["publish"] is True


def test_persist_profile_behavior(adapter):
    """Behavior: Profiles are persisted to profiles_dir/{uuid}/{slug}.md."""
    uuid = "123e4567-e89b-12d3-a456-426614174000"
    doc = Document(
        content="Profile bio",
        type=DocumentType.PROFILE,
        metadata={
            "uuid": uuid,
            "subject": uuid,  # Required by _url_to_path
            "slug": "jane-doe",
            "name": "Jane Doe",
        },
        id="profile-123",
    )

    with patch.object(
        adapter._url_convention, "canonical_url", return_value=f"https://example.com/authors/{uuid}/jane-doe"
    ):
        adapter.persist(doc)

    expected_path = adapter.profiles_dir / uuid / "jane-doe.md"
    assert expected_path.exists()

    post = frontmatter.load(expected_path)
    assert post.content.strip() == "Profile bio"
    assert post.metadata["type"] == "profile"
    assert "Authors" in post.metadata["categories"]
    assert "avatar" in post.metadata  # Should generate fallback


def test_persist_profile_missing_uuid_raises(adapter):
    """Behavior: Persisting a profile without UUID raises ProfileMetadataError."""
    doc = Document(
        content="Invalid profile", type=DocumentType.PROFILE, metadata={"slug": "no-uuid"}, id="profile-bad"
    )

    with pytest.raises(ProfileMetadataError):
        adapter.persist(doc)


def test_persist_enrichment_url_behavior(adapter):
    """Behavior: Enrichment URLs are persisted to media_dir/urls/{slug}.md."""
    doc = Document(
        content="Link description",
        type=DocumentType.ENRICHMENT_URL,
        metadata={"slug": "some-link", "url": "https://example.com"},
        id="enrich-1",
    )

    with patch.object(
        adapter._url_convention, "canonical_url", return_value="https://example.com/media/urls/some-link"
    ):
        adapter.persist(doc)

    expected_path = adapter.media_dir / "urls" / "some-link.md"
    assert expected_path.exists()

    post = frontmatter.load(expected_path)
    assert post.metadata["slug"] == "some-link"
    assert "Enrichment" in post.metadata["categories"]
    assert "navigation" in post.metadata["hide"]  # Hidden


def test_persist_enrichment_url_collision_behavior(adapter):
    """Behavior: Enrichment URL collisions are resolved by appending counters."""
    doc1 = Document(
        content="First",
        type=DocumentType.ENRICHMENT_URL,
        metadata={"slug": "collision", "url": "https://example.com/1"},
        id="id-1",
    )
    doc2 = Document(
        content="Second",
        type=DocumentType.ENRICHMENT_URL,
        metadata={"slug": "collision", "url": "https://example.com/2"},
        id="id-2",
    )

    with patch.object(
        adapter._url_convention, "canonical_url", return_value="https://example.com/media/urls/collision"
    ):
        adapter.persist(doc1)
        adapter.persist(doc2)

    path1 = adapter.media_dir / "urls" / "collision.md"
    path2 = adapter.media_dir / "urls" / "collision-1.md"

    assert path1.exists()
    assert path2.exists()

    assert frontmatter.load(path1).content.strip() == "First"
    assert frontmatter.load(path2).content.strip() == "Second"


def test_persist_media_behavior(adapter):
    """Behavior: Media content is written to file."""
    doc = Document(content=b"binarydata", type=DocumentType.MEDIA, metadata={}, id="media-1")

    with patch.object(
        adapter._url_convention, "canonical_url", return_value="https://example.com/media/image.png"
    ):
        adapter.persist(doc)

    expected_path = adapter.media_dir / "image.png"
    assert expected_path.exists()
    assert expected_path.read_bytes() == b"binarydata"


def test_persist_media_with_source_path_behavior(adapter, tmp_path):
    """Behavior: Media with source_path is moved/copied."""
    source_file = tmp_path / "source.png"
    source_file.write_bytes(b"sourcedata")

    doc = Document(
        content=b"", type=DocumentType.MEDIA, metadata={"source_path": str(source_file)}, id="media-source"
    )

    with patch.object(
        adapter._url_convention, "canonical_url", return_value="https://example.com/media/moved.png"
    ):
        adapter.persist(doc)

    expected_path = adapter.media_dir / "moved.png"
    assert expected_path.exists()
    assert expected_path.read_bytes() == b"sourcedata"


def test_persist_pii_skipped(adapter, caplog):
    """Behavior: Media with pii_deleted=True is skipped."""
    doc = Document(content=b"secret", type=DocumentType.MEDIA, metadata={"pii_deleted": True}, id="pii-doc")

    with caplog.at_level(logging.INFO):
        with patch.object(
            adapter._url_convention, "canonical_url", return_value="https://example.com/media/secret.png"
        ):
            adapter.persist(doc)

    expected_path = adapter.media_dir / "secret.png"
    assert not expected_path.exists()
    assert "Skipping persistence of PII-containing media" in caplog.text


def test_persist_write_error_handling(adapter):
    """Behavior: FileWriteError is raised on IO issues."""
    doc = Document(content="fail", type=DocumentType.JOURNAL, metadata={"slug": "fail"}, id="fail-1")

    # Mock Path.write_text to raise OSError
    with patch("pathlib.Path.write_text", side_effect=OSError("Disk full")):
        with pytest.raises(FileWriteError):
            adapter.persist(doc)


def test_resolve_document_path_behavior(adapter):
    """Behavior: Resolves relative storage identifiers to absolute paths."""
    # Setup some structure
    (adapter.posts_dir / "test-post.md").touch()

    # identifier is relative to site_root
    rel_to_root = adapter.posts_dir.relative_to(adapter.site_root) / "test-post.md"

    # Test valid resolution
    path = adapter.resolve_document_path(str(rel_to_root))
    assert path.is_absolute()
    assert path == adapter.posts_dir / "test-post.md"


def test_resolve_document_path_not_initialized():
    """Behavior: Raises AdapterNotInitializedError if not initialized."""
    adapter = MkDocsAdapter()
    # No initialize call
    with pytest.raises(AdapterNotInitializedError):
        adapter.resolve_document_path("something")


def test_scaffold_authors_file(adapter):
    """Behavior: Ensures .authors.yml exists in docs dir."""
    # It is called in scaffold_site, but also we can check if it creates it if missing.
    # _scaffold_authors_file is "private" but called by scaffold_site.
    # Let's call scaffold_site.

    # Mock the internal scaffolder to do nothing
    with patch.object(adapter._scaffolder, "scaffold_site") as mock_scaffold:
        mock_scaffold.return_value = (adapter.site_root, True)
        adapter.scaffold_site(adapter.site_root, "My Site")

    authors_file = adapter.docs_dir / ".authors.yml"
    assert authors_file.exists()
    assert "# Authors metadata" in authors_file.read_text()

    # Verify it doesn't overwrite existing
    authors_file.write_text("existing: data")
    with patch.object(adapter._scaffolder, "scaffold_site") as mock_scaffold:
        mock_scaffold.return_value = (adapter.site_root, True)
        adapter.scaffold_site(adapter.site_root, "My Site")

    assert authors_file.read_text() == "existing: data"


def test_scaffold_site_delegation(adapter):
    """Behavior: Delegates scaffolding to internal scaffolder."""
    with patch.object(adapter._scaffolder, "scaffold_site") as mock_scaffold:
        mock_scaffold.return_value = (adapter.site_root, True)
        result = adapter.scaffold_site(adapter.site_root, "My Site", foo="bar")

        mock_scaffold.assert_called_once_with(adapter.site_root, "My Site", foo="bar")
        assert result == (adapter.site_root, True)


def test_list_behavior(adapter):
    """Behavior: Lists documents from filesystem."""
    # Create some dummy files
    (adapter.posts_dir / "2025-01-01-p1.md").write_text("---\nslug: p1\n---\nPost 1")
    (adapter.journal_dir / "j1.md").write_text("---\nslug: j1\ncategories: [Journal]\n---\nJournal 1")

    docs = list(adapter.list())
    identifiers = [d.identifier for d in docs]

    # Identifier format: relative to site root
    # posts/2025-01-01-p1.md
    # posts/journal/j1.md (assuming journal_dir is posts/journal)

    assert any("p1.md" in i for i in identifiers)

    # Verify journal directory location relative to posts_dir to understand listing behavior
    try:
        adapter.journal_dir.relative_to(adapter.posts_dir)
        is_in_posts = True
    except ValueError:
        is_in_posts = False

    if is_in_posts:
        assert any("j1.md" in i for i in identifiers)
        # Test filtering
        journal_docs = list(adapter.list(doc_type=DocumentType.JOURNAL))
        assert len(journal_docs) == 1
        assert "j1.md" in journal_docs[0].identifier


def test_get_document_from_db_behavior(adapter):
    """Behavior: Retrieves document from storage backend."""
    mock_storage = Mock()
    adapter._storage = mock_storage

    # Mock return for post
    mock_table = Mock()
    mock_df = Mock()
    mock_df.iloc = [{"content": "---\ntitle: Post\n---\nContent"}]
    mock_df.__len__ = Mock(return_value=1)
    mock_table.filter.return_value.execute.return_value = mock_df
    mock_storage.read_table.return_value = mock_table

    doc = adapter.get(DocumentType.POST, "my-slug")

    assert doc.type == DocumentType.POST
    assert doc.metadata["title"] == "Post"
    assert doc.content == "Content"


def test_get_document_not_found(adapter):
    """Behavior: Raises DocumentNotFoundError if not in DB."""
    mock_storage = Mock()
    adapter._storage = mock_storage

    mock_table = Mock()
    mock_table.filter.return_value.execute.return_value = []  # Empty result
    mock_storage.read_table.return_value = mock_table

    with pytest.raises(DocumentNotFoundError):
        adapter.get(DocumentType.POST, "missing")


def test_documents_iterator_behavior(adapter):
    """Behavior: Iterates over all documents from DB."""
    mock_storage = Mock()
    adapter._storage = mock_storage

    # Mock posts table
    posts_table = Mock()
    posts_df = Mock()
    # Mock iterrows
    posts_df.iterrows.return_value = [
        (0, {"content": "---\ntitle: P1\n---\nC1"}),
        (1, {"content": "---\ntitle: P2\n---\nC2"}),
    ]
    posts_table.execute.return_value = posts_df

    # Mock profiles table
    profiles_table = Mock()
    profiles_df = Mock()
    profiles_df.iterrows.return_value = [(0, {"content": "---\nname: A1\n---\nBio"})]
    profiles_table.execute.return_value = profiles_df

    def read_table_side_effect(name):
        if name == "posts":
            return posts_table
        if name == "profiles":
            return profiles_table
        raise KeyError(name)

    mock_storage.read_table.side_effect = read_table_side_effect

    docs = list(adapter.documents())
    assert len(docs) == 3
    assert len([d for d in docs if d.type == DocumentType.POST]) == 2
    assert len([d for d in docs if d.type == DocumentType.PROFILE]) == 1


def test_load_config_behavior(adapter):
    """Behavior: Loads mkdocs.yml configuration."""
    egregora_dir = adapter.site_root / ".egregora"
    egregora_dir.mkdir(exist_ok=True)
    (egregora_dir / "mkdocs.yml").write_text("site_name: Test Site\nmarkdown_extensions:\n  - foo")

    config = adapter.load_config(adapter.site_root)
    assert config["site_name"] == "Test Site"
    assert "foo" in adapter.get_markdown_extensions()


def test_get_format_instructions(adapter):
    """Behavior: Returns formatting instructions."""
    instr = adapter.get_format_instructions()
    assert "MkDocs Material" in instr
    assert "Front-matter Format" in instr


def test_initialize_filesystem_error(tmp_path):
    """Behavior: Raises DirectoryCreationError if initialization fails."""
    # Pass a file as site_root, ensuring mkdir fails
    site_root = tmp_path / "file"
    site_root.touch()

    adapter = MkDocsAdapter()
    with pytest.raises(Exception):  # noqa: B017
        adapter.initialize(site_root=site_root)
