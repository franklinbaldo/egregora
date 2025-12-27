from __future__ import annotations

from pathlib import Path

import pytest

from egregora.data_primitives.document import Document, DocumentType
from egregora.output_adapters.exceptions import (
    ProfileNotFoundError,
    ProfileGenerationError,
    CollisionResolutionError,
    DocumentNotFoundError,
)
from egregora.output_adapters.mkdocs.adapter import MkDocsAdapter


@pytest.fixture
def mkdocs_adapter(tmp_path: Path) -> MkDocsAdapter:
    """Provides an initialized MkDocsAdapter in a temporary directory."""
    adapter = MkDocsAdapter()
    adapter.initialize(tmp_path)
    return adapter


def test_write_post_doc(mkdocs_adapter: MkDocsAdapter, tmp_path: Path):
    """Verify _write_post_doc writes correct frontmatter and content."""
    doc = Document(
        content="This is the post content.",
        type=DocumentType.POST,
        metadata={
            "title": "Test Post",
            "date": "2024-01-01",
            "authors": ["author-uuid-1"],
            "tags": ["testing", "refactor"],
            "summary": "A test post summary.",
        },
    )
    post_path = tmp_path / "test-post.md"
    mkdocs_adapter._write_post_doc(doc, post_path)

    assert post_path.exists()
    content = post_path.read_text()
    assert "title: Test Post" in content
    assert "date: 2024-01-01" in content
    assert "summary: A test post summary." in content
    assert "---" in content
    assert "This is the post content." in content


def test_write_journal_doc(mkdocs_adapter: MkDocsAdapter, tmp_path: Path):
    """Verify _write_journal_doc adds 'Journal' category."""
    doc = Document(
        content="This is a journal entry.", type=DocumentType.JOURNAL, metadata={"title": "Journal Entry"}
    )
    journal_path = tmp_path / "journal-entry.md"
    mkdocs_adapter._write_journal_doc(doc, journal_path)

    assert journal_path.exists()
    content = journal_path.read_text()
    assert "categories:" in content
    assert "- Journal" in content
    assert "This is a journal entry." in content


def test_write_annotation_doc(mkdocs_adapter: MkDocsAdapter, tmp_path: Path):
    """Verify _write_annotation_doc adds 'Annotations' category."""
    doc = Document(
        content="This is an annotation.", type=DocumentType.ANNOTATION, metadata={"title": "Annotation"}
    )
    annotation_path = tmp_path / "annotation.md"
    mkdocs_adapter._write_annotation_doc(doc, annotation_path)

    assert annotation_path.exists()
    content = annotation_path.read_text()
    assert "categories:" in content
    assert "- Annotations" in content
    assert "This is an annotation." in content


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
    # More precise check: verify avatar URL starts with expected domain
    # This satisfies CodeQL by using startswith() instead of substring check
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


def test_write_media_doc_from_content(mkdocs_adapter: MkDocsAdapter, tmp_path: Path):
    """Verify _write_media_doc writes binary content correctly."""
    media_content = b"This is a media file."
    doc = Document(content=media_content, type=DocumentType.MEDIA, metadata={"filename": "media.txt"})
    media_path = tmp_path / "media.txt"
    mkdocs_adapter._write_media_doc(doc, media_path)

    assert media_path.exists()
    assert media_path.read_bytes() == media_content


def test_write_media_doc_from_source_path(mkdocs_adapter: MkDocsAdapter, tmp_path: Path):
    """Verify _write_media_doc moves a file from a source path."""
    source_content = b"This is the source media file."
    source_path = tmp_path / "source_media.txt"
    source_path.write_bytes(source_content)

    doc = Document(
        content="",  # Content should be ignored
        type=DocumentType.MEDIA,
        metadata={"source_path": str(source_path)},
    )
    media_path = tmp_path / "destination_media.txt"
    mkdocs_adapter._write_media_doc(doc, media_path)

    assert media_path.exists()
    assert not source_path.exists()  # shutil.move should remove the source
    assert media_path.read_bytes() == source_content


def test_get_author_profile_raises_not_found(mkdocs_adapter):
    """
    Given an author UUID that does not exist
    When get_author_profile is called
    Then it should raise ProfileNotFoundError.
    """
    with pytest.raises(ProfileNotFoundError):
        mkdocs_adapter.get_author_profile("non-existent-uuid")


def test_write_profile_doc_raises_generation_error_on_missing_uuid(mkdocs_adapter):
    """
    Given a profile document with no UUID in its metadata
    When _write_profile_doc is called
    Then it should raise a ProfileGenerationError.
    """
    doc = Document(
        content="This is a profile.",
        type=DocumentType.PROFILE,
        metadata={"name": "Test Author"},  # Missing 'uuid'
    )
    profile_path = Path("/fake/path.md")
    with pytest.raises(ProfileGenerationError):
        mkdocs_adapter._write_profile_doc(doc, profile_path)


def test_resolve_collision_raises_error_after_max_attempts(mkdocs_adapter, tmp_path):
    """
    Given a path with many conflicting files
    When _resolve_collision is called with a low max_attempts
    Then it should raise a CollisionResolutionError.
    """
    base_path = tmp_path / "test.txt"
    base_path.touch()
    max_attempts = 3
    for i in range(1, max_attempts + 2):
        # Create colliding files that _resolve_collision will find
        (tmp_path / f"test-{i}.txt").touch()

    # Mock _get_document_id_at_path to always return a conflicting ID
    with pytest.MonkeyPatch.context() as m:
        m.setattr(mkdocs_adapter, '_get_document_id_at_path', lambda path: "some-other-id")

        with pytest.raises(CollisionResolutionError) as excinfo:
            # Call the method with a low max_attempts value
            mkdocs_adapter._resolve_collision(base_path, "new-doc-id", max_attempts=max_attempts)

        assert excinfo.value.path == str(base_path)
        assert excinfo.value.max_attempts == max_attempts


def test_get_raises_not_found_error(mkdocs_adapter):
    """
    Given a document type and an identifier that does not exist
    When get is called
    Then it should raise DocumentNotFoundError.
    """
    with pytest.raises(DocumentNotFoundError):
        mkdocs_adapter.get(DocumentType.POST, "non-existent-post")
