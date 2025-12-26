from __future__ import annotations

from pathlib import Path

import pytest

from egregora.data_primitives.document import Document, DocumentType
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
    assert "https://avataaars.io" in content
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
