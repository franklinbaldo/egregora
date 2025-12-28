from __future__ import annotations

from pathlib import Path

import pytest
from unittest.mock import patch

from egregora.data_primitives.document import Document, DocumentType, UrlContext
from egregora.output_adapters.exceptions import (
    AdapterNotInitializedError,
    CollisionResolutionError,
    ConfigLoadError,
    DocumentNotFoundError,
    DocumentParsingError,
    IncompleteProfileError,
    ProfileGenerationError,
    ProfileMetadataError,
    ProfileNotFoundError,
    UnsupportedDocumentTypeError,
)
from egregora.output_adapters.mkdocs.adapter import MkDocsAdapter


@pytest.fixture
def mkdocs_adapter(tmp_path: Path) -> MkDocsAdapter:
    """Provides an initialized MkDocsAdapter in a temporary directory."""
    adapter = MkDocsAdapter()
    url_context = UrlContext(base_url="http://localhost", site_prefix="", base_path=tmp_path)
    adapter.initialize(tmp_path, url_context=url_context)
    return adapter

def test_get_raises_document_not_found_error(mkdocs_adapter: MkDocsAdapter):
    """Verify get() raises DocumentNotFoundError for a non-existent document."""
    with pytest.raises(DocumentNotFoundError):
        mkdocs_adapter.get(DocumentType.POST, "non-existent-slug")

def test_document_from_path_raises_document_parsing_error(mkdocs_adapter: MkDocsAdapter):
    """Verify _document_from_path() raises DocumentParsingError on OSError."""
    with patch("frontmatter.load", side_effect=OSError("Test file read error")):
        with pytest.raises(DocumentParsingError):
            mkdocs_adapter._document_from_path(Path("non-existent.md"), DocumentType.POST)

def test_get_author_profile_raises_profile_not_found_error(mkdocs_adapter: MkDocsAdapter):
    """Verify get_author_profile() raises ProfileNotFoundError for a non-existent author."""
    with pytest.raises(ProfileNotFoundError):
        mkdocs_adapter.get_author_profile("non-existent-uuid")

def test_get_document_id_at_path_raises_document_not_found_error(mkdocs_adapter: MkDocsAdapter):
    """Verify _get_document_id_at_path() raises DocumentNotFoundError for a non-existent file."""
    with pytest.raises(DocumentNotFoundError):
        mkdocs_adapter._get_document_id_at_path(Path("non-existent.md"))

def test_get_document_id_at_path_raises_document_parsing_error(mkdocs_adapter: MkDocsAdapter, tmp_path):
    """Verify _get_document_id_at_path() raises DocumentParsingError on OSError."""
    mock_path = tmp_path / "mocked-existent.md"
    mock_path.touch()
    with patch.object(Path, "read_text", side_effect=OSError("Test read error")):
        with pytest.raises(DocumentParsingError):
            mkdocs_adapter._get_document_id_at_path(mock_path)

def test_load_config_raises_config_load_error_on_file_not_found(mkdocs_adapter: MkDocsAdapter):
    """Verify load_config() raises ConfigLoadError when mkdocs.yml is missing."""
    with pytest.raises(ConfigLoadError):
        mkdocs_adapter.load_config(mkdocs_adapter.site_root)

def test_load_config_raises_config_load_error_on_yaml_error(mkdocs_adapter: MkDocsAdapter, tmp_path):
    """Verify load_config() raises ConfigLoadError on YAMLError."""
    mkdocs_yml_path = tmp_path / "mkdocs.yml"
    mkdocs_yml_path.write_text("invalid: yaml: here")
    with patch("egregora.output_adapters.mkdocs.paths.MkDocsPaths.mkdocs_path", mkdocs_yml_path):
        with pytest.raises(ConfigLoadError):
            mkdocs_adapter.load_config(tmp_path)

def test_resolve_document_path_raises_unsupported_type_error(mkdocs_adapter: MkDocsAdapter):
    """Verify _resolve_document_path() raises UnsupportedDocumentTypeError for an unsupported type."""
    with pytest.raises(UnsupportedDocumentTypeError):
        mkdocs_adapter._resolve_document_path("unsupported", "some-id")

def test_get_raises_document_parsing_error(mkdocs_adapter: MkDocsAdapter):
    """Verify get() raises DocumentParsingError for a malformed document file."""
    post_path = mkdocs_adapter.posts_dir / "2024-01-01-malformed-post.md"
    post_path.write_text("---\ntitle: Malformed\ninvalid_yaml: [\n---")
    with pytest.raises(DocumentParsingError):
        mkdocs_adapter.get(DocumentType.POST, "malformed-post")

def test_write_post_doc(mkdocs_adapter: MkDocsAdapter, tmp_path: Path):
    """Verify _write_post_doc writes correct frontmatter and content."""
    doc = Document(
        content="This is the post content.",
        type=DocumentType.POST,
        metadata={
            "title": "Test Post", "date": "2024-01-01", "authors": ["author-uuid-1"],
            "tags": ["testing", "refactor"], "summary": "A test post summary.",
        },
    )
    post_path = tmp_path / "test-post.md"
    mkdocs_adapter._write_post_doc(doc, post_path)
    assert post_path.exists()
    content = post_path.read_text()
    assert "title: Test Post" in content
    assert "This is the post content." in content

def test_write_journal_doc(mkdocs_adapter: MkDocsAdapter, tmp_path: Path):
    """Verify _write_journal_doc adds 'Journal' category."""
    doc = Document(content="journal entry.", type=DocumentType.JOURNAL, metadata={"title": "Journal"})
    journal_path = tmp_path / "journal-entry.md"
    mkdocs_adapter._write_journal_doc(doc, journal_path)
    assert journal_path.exists()
    content = journal_path.read_text()
    assert "- Journal" in content
    assert "journal entry." in content

def test_write_annotation_doc(mkdocs_adapter: MkDocsAdapter, tmp_path: Path):
    """Verify _write_annotation_doc adds 'Annotations' category."""
    doc = Document(content="annotation.", type=DocumentType.ANNOTATION, metadata={"title": "Annotation"})
    annotation_path = tmp_path / "annotation.md"
    mkdocs_adapter._write_annotation_doc(doc, annotation_path)
    assert annotation_path.exists()
    content = annotation_path.read_text()
    assert "- Annotations" in content
    assert "annotation." in content

def test_write_profile_doc(mkdocs_adapter: MkDocsAdapter, tmp_path: Path):
    """Verify _write_profile_doc adds fallback avatar and 'Profile' category."""
    author_uuid = "a-unique-author-uuid"
    doc = Document(
        content="This is a profile.",
        type=DocumentType.PROFILE,
        metadata={"uuid": author_uuid, "name": "Test Author"},
    )
    profile_path = tmp_path / "profile.md"
    mkdocs_adapter._write_profile_doc(doc, profile_path)
    assert profile_path.exists()
    content = profile_path.read_text()
    assert "categories:" in content
    assert "- Profile" in content
    assert "avatar:" in content
    assert any(line.strip().startswith("avatar: https://avataaars.io/") for line in content.split("\n"))
    assert "This is a profile." in content

def test_write_enrichment_doc(mkdocs_adapter: MkDocsAdapter, tmp_path: Path):
    """Verify _write_enrichment_doc adds 'Enrichment' category."""
    doc = Document(
        content="This is an enrichment.", type=DocumentType.ENRICHMENT_URL, metadata={"title": "Enrichment"}
    )
    enrichment_path = tmp_path / "enrichment.md"
    mkdocs_adapter._write_enrichment_doc(doc, enrichment_path)
    assert enrichment_path.exists()
    content = enrichment_path.read_text()
    assert "categories:" in content
    assert "- Enrichment" in content
    assert "This is an enrichment." in content

def test_write_profile_doc_raises_on_missing_uuid(mkdocs_adapter):
    """Verify _write_profile_doc raises ProfileGenerationError on missing UUID."""
    doc = Document(content="profile.", type=DocumentType.PROFILE, metadata={"name": "Test Author"})
    with pytest.raises(ProfileGenerationError):
        mkdocs_adapter._write_profile_doc(doc, Path("/fake/path.md"))

def test_write_media_doc_from_content(mkdocs_adapter: MkDocsAdapter, tmp_path: Path):
    """Verify _write_media_doc writes binary content correctly."""
    media_content = b"media file."
    doc = Document(content=media_content, type=DocumentType.MEDIA, metadata={"filename": "media.txt"})
    media_path = tmp_path / "media.txt"
    mkdocs_adapter._write_media_doc(doc, media_path)
    assert media_path.exists()
    assert media_path.read_bytes() == media_content

def test_write_media_doc_from_source_path(mkdocs_adapter: MkDocsAdapter, tmp_path: Path):
    """Verify _write_media_doc moves a file from a source path."""
    source_content = b"source media."
    source_path = tmp_path / "source_media.txt"
    source_path.write_bytes(source_content)
    doc = Document(content="", type=DocumentType.MEDIA, metadata={"source_path": str(source_path)})
    media_path = tmp_path / "destination_media.txt"
    mkdocs_adapter._write_media_doc(doc, media_path)
    assert media_path.exists()
    assert not source_path.exists()
    assert media_path.read_bytes() == source_content

def test_resolve_collision_raises_error_after_max_attempts(mkdocs_adapter, tmp_path):
    """Verify _resolve_collision raises CollisionResolutionError after max attempts."""
    base_path = tmp_path / "test.txt"
    base_path.touch()
    max_attempts = 3
    for i in range(1, max_attempts + 2):
        (tmp_path / f"test-{i}.txt").touch()
    with patch.object(mkdocs_adapter, "_get_document_id_at_path", return_value="some-other-id"):
        with pytest.raises(CollisionResolutionError) as excinfo:
            mkdocs_adapter._resolve_collision(base_path, "new-doc-id", max_attempts=max_attempts)
        assert excinfo.value.path == str(base_path)
        assert excinfo.value.max_attempts == max_attempts

def test_resolve_document_path_raises_adapter_not_initialized_error():
    """Verify calling resolve_document_path on an uninitialized adapter raises an error."""
    adapter = MkDocsAdapter()
    with pytest.raises(AdapterNotInitializedError):
        adapter.resolve_document_path("some/path.md")


# --- Sapper's New Exception Tests ---

AUTHOR_UUID = "d944f0f7-9226-4880-a6a2-11a3d2d472b1"


def test_build_author_profile_raises_incomplete_error_if_no_name(mkdocs_adapter: MkDocsAdapter, tmp_path: Path):
    """Test that _build_author_profile raises IncompleteProfileError if no name is ever found."""
    author_dir = tmp_path / "posts" / "authors" / AUTHOR_UUID
    author_dir.mkdir(parents=True, exist_ok=True)
    mkdocs_adapter.posts_dir = tmp_path / "posts"


    # Create a post file with frontmatter that is missing the author's name
    post_content = f\"\"\"---
title: A Post Without Author Name
date: 2024-01-01
authors:
  - uuid: {AUTHOR_UUID}
    # 'name' field is intentionally omitted
    bio: "A bio."
---

Content of the post.
\"\"\"
    (author_dir / "2024-01-01-post.md").write_text(post_content)

    with pytest.raises(IncompleteProfileError, match="Profile for author .* is incomplete: No name found"):
        mkdocs_adapter._build_author_profile(AUTHOR_UUID)


def test_get_profiles_data_raises_on_corrupt_file(mkdocs_adapter: MkDocsAdapter, tmp_path: Path):
    """Test that get_profiles_data raises DocumentParsingError for a corrupt profile file."""
    # Setup a valid directory structure
    profiles_dir = tmp_path / "profiles"
    mkdocs_adapter.profiles_dir = profiles_dir
    author_dir = profiles_dir / AUTHOR_UUID
    author_dir.mkdir(parents=True, exist_ok=True)

    # Create a profile file with invalid YAML frontmatter
    corrupt_content = \"\"\"---
title: Corrupt Profile
date: 2024-01-01
authors: [
---
This file has unclosed YAML.
\"\"\"
    profile_path = author_dir / "profile.md"
    profile_path.write_text(corrupt_content)

    # The adapter needs a documents() method that returns something for this test.
    # Let's mock it to return an empty list to isolate the parsing logic.
    mkdocs_adapter.documents = lambda: []

    with pytest.raises(DocumentParsingError, match=f"Failed to parse document at '{profile_path}'"):
        mkdocs_adapter.get_profiles_data()


def test_get_recent_media_raises_on_corrupt_file(mkdocs_adapter: MkDocsAdapter, tmp_path: Path):
    """Test that get_recent_media raises DocumentParsingError for a corrupt media file."""
    # Setup a valid directory structure
    urls_dir = tmp_path / "media" / "urls"
    urls_dir.mkdir(parents=True, exist_ok=True)
    mkdocs_adapter.urls_dir = urls_dir

    # Create a media file with invalid YAML frontmatter
    corrupt_content = \"\"\"---
title: Corrupt Media
url: http://example.com
summary: [
---
This file has unclosed YAML.
\"\"\"
    media_path = urls_dir / "corrupt-media.md"
    media_path.write_text(corrupt_content)

    with pytest.raises(DocumentParsingError, match=f"Failed to parse document at '{media_path}'"):
        mkdocs_adapter.get_recent_media()


def test_url_to_path_raises_for_profile_missing_subject(mkdocs_adapter: MkDocsAdapter):
    """Test _url_to_path raises ProfileMetadataError for a PROFILE doc missing 'subject'."""
    # Create a document of type PROFILE but without the 'subject' metadata
    profile_doc = Document(
        content="This is a profile.",
        type=DocumentType.PROFILE,
        metadata={"title": "A Profile", "slug": "a-profile"},  # Missing 'subject'
    )
    doc_id = profile_doc.document_id

    # The URL context is needed for the method to run
    mkdocs_adapter._ctx = UrlContext(base_url="http://localhost:8000", site_prefix="", base_path=Path.cwd())

    with pytest.raises(ProfileMetadataError, match=f"PROFILE document '{doc_id}' missing required metadata field: 'subject'"):
        # The URL can be simple for this test, as the logic branch is determined by doc type
        mkdocs_adapter._url_to_path("/profiles/a-profile", profile_doc)


# ============================================================================
# Phase 2: Dynamic Site Generation Tests
# ============================================================================

def test_regenerate_main_index(mkdocs_adapter: MkDocsAdapter):
    """Verify regenerate_main_index creates index.md with correct content."""
    # 1. Mock the data-fetching methods
    mock_stats_data = {'post_count': 10, 'profile_count': 5, 'media_count': 20, 'journal_count': 2}
    mock_media_data = [{'title': 'Recent Media Item', 'url': '/media/recent', 'summary': 'A summary.'}]
    mock_profiles_data = [{'name': 'Dr. Test Author', 'uuid': 'uuid1', 'bio': 'Bio of test author.', 'post_count': 5}]

    with patch.object(mkdocs_adapter, 'get_site_stats', return_value=mock_stats_data) as mock_stats, \
         patch.object(mkdocs_adapter, 'get_recent_media', return_value=mock_media_data) as mock_media, \
         patch.object(mkdocs_adapter, 'get_profiles_data', return_value=mock_profiles_data) as mock_profiles:

        # 2. Call the method
        mkdocs_adapter.regenerate_main_index()

        # 3. Verify file creation
        index_path = mkdocs_adapter.docs_dir / "index.md"
        assert index_path.exists(), "index.md was not created"

        # 4. Verify content
        content = index_path.read_text()
        assert "10</strong> Posts" in content
        assert "5</strong> Profiles" in content
        assert "20</strong> Media" in content
        assert "2</strong> Journal" in content
        assert "Recent Media Item" in content
        assert "Dr. Test Author" in content

        # 5. Verify mocks were called
        mock_stats.assert_called_once()
        mock_media.assert_called_once_with(limit=5)
        mock_profiles.assert_called_once()

def test_regenerate_profiles_index(mkdocs_adapter: MkDocsAdapter):
    """Verify regenerate_profiles_index creates index.md with correct profile data."""
    # 1. Mock the data-fetching method
    mock_profiles_data = [
        {'name': 'Author One', 'uuid': 'uuid1', 'bio': 'Bio 1', 'post_count': 10, 'avatar': '/path/to/avatar1.png'},
        {'name': 'Author Two', 'uuid': 'uuid2', 'bio': 'Bio 2', 'post_count': 5, 'avatar': '/path/to/avatar2.png'}
    ]

    with patch.object(mkdocs_adapter, 'get_profiles_data', return_value=mock_profiles_data) as mock_profiles:
        # 2. Call the method
        mkdocs_adapter.regenerate_profiles_index()

        # 3. Verify file creation
        index_path = mkdocs_adapter.profiles_dir / "index.md"
        assert index_path.exists(), "profiles/index.md was not created"

        # 4. Verify content
        content = index_path.read_text()
        assert "Profiles" in content
        assert "Author One" in content
        assert "Bio 2" in content
        assert "10 Posts" in content
        assert "(5 Posts)" in content  # Check post count formatting

        # 5. Verify mock was called
        mock_profiles.assert_called_once()

def test_regenerate_media_index(mkdocs_adapter: MkDocsAdapter):
    """Verify regenerate_media_index creates index.md with correct media data."""
    # 1. Mock the data-fetching method
    mock_media_data = [
        {'title': 'Media One', 'url': '/media/one', 'summary': 'Summary 1.'},
        {'title': 'Media Two', 'url': '/media/two', 'summary': 'Summary 2.'}
    ]

    with patch.object(mkdocs_adapter, 'get_recent_media', return_value=mock_media_data) as mock_media:
        # 2. Call the method
        mkdocs_adapter.regenerate_media_index()

        # 3. Verify file creation
        index_path = mkdocs_adapter.media_dir / "index.md"
        assert index_path.exists(), "media/index.md was not created"

        # 4. Verify content
        content = index_path.read_text()
        assert "Media Index" in content
        assert "Media One" in content
        assert "Summary 2." in content

        # 5. Verify mock was called
        mock_media.assert_called_once_with(limit=50)

def test_finalize_window_calls_regenerate_methods(mkdocs_adapter: MkDocsAdapter):
    """Verify finalize_window() calls all the necessary regenerate methods."""
    with patch.object(mkdocs_adapter, 'regenerate_main_index') as mock_main, \
         patch.object(mkdocs_adapter, 'regenerate_profiles_index') as mock_profiles, \
         patch.object(mkdocs_adapter, 'regenerate_media_index') as mock_media, \
         patch.object(mkdocs_adapter, 'regenerate_tags_page') as mock_tags:

        mkdocs_adapter.finalize_window("test-window", [], [], {})

        mock_main.assert_called_once()
        mock_profiles.assert_called_once()
        mock_media.assert_called_once()
        mock_tags.assert_called_once()
