from __future__ import annotations

from datetime import UTC, datetime

from egregora.agents.shared.annotations import ANNOTATION_AUTHOR, Annotation, AnnotationStore
from egregora.data_primitives.document import DocumentType


def test_annotation_to_document_roundtrip_metadata():
    created_at = datetime(2025, 1, 11, 12, 30, tzinfo=UTC)
    annotation = Annotation(
        id=42,
        parent_id="message-123",
        parent_type="message",
        author=ANNOTATION_AUTHOR,
        commentary="Remember to highlight the user's main concern.",
        created_at=created_at,
    )

    document = annotation.to_document()

    assert document.type is DocumentType.ANNOTATION
    assert document.content.endswith(annotation.commentary)
    assert "annotation_id: 42" in document.content
    assert document.metadata["annotation_id"] == str(annotation.id)
    assert document.metadata["title"] == "Annotation 42"
    assert document.metadata["parent_id"] == annotation.parent_id
    assert document.metadata["parent_type"] == annotation.parent_type
    assert document.metadata["author"] == annotation.author
    assert document.created_at == created_at


def test_store_iterates_annotations_as_documents(tmp_path):
    store = AnnotationStore(tmp_path / "annotations.duckdb")
    note_a = store.save_annotation("message-1", "message", "First note")
    note_b = store.save_annotation(str(note_a.id), "annotation", "Second layer")

    documents = list(store.iter_annotation_documents())

    assert [doc.metadata["annotation_id"] for doc in documents] == [str(note_a.id), str(note_b.id)]
    assert all(doc.type is DocumentType.ANNOTATION for doc in documents)


def test_annotation_documents_preserve_unique_identity():
    created_at = datetime(2025, 1, 11, 12, 30, tzinfo=UTC)
    first = Annotation(
        id=1,
        parent_id="message-123",
        parent_type="message",
        author=ANNOTATION_AUTHOR,
        commentary="TODO",
        created_at=created_at,
    )
    second = Annotation(
        id=2,
        parent_id="message-456",
        parent_type="message",
        author=ANNOTATION_AUTHOR,
        commentary="TODO",
        created_at=created_at,
    )

    doc_a = first.to_document()
    doc_b = second.to_document()

    assert doc_a.document_id != doc_b.document_id
    assert doc_a.content.endswith(first.commentary)
    assert doc_b.content.endswith(second.commentary)
