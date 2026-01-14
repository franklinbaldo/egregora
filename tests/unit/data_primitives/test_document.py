from __future__ import annotations
import pytest

from egregora.data_primitives.document import Document, DocumentType


@pytest.mark.parametrize(
    ("content", "metadata", "expected_slug"),
    [
        ("test content", {}, "da947fba"),
        ("test content", {"slug": "   "}, "da947fba"),
        ("different content", {}, "b578faa2"),
        (b"binary content", {}, "6bc78833"),
    ],
    ids=[
        "no_slug_falls_back_to_uuid",
        "blank_slug_falls_back_to_uuid",
        "different_content_different_uuid",
        "binary_content_uuid",
    ],
)
def test_slug_fallback_behavior(content: str | bytes, metadata: dict, expected_slug: str):
    """Verify that slug property falls back to UUID when no slug is provided."""
    doc = Document(content=content, type=DocumentType.POST, metadata=metadata)
    assert doc.slug == expected_slug


def test_slug_uses_metadata_when_present():
    """Verify that slug property uses slug from metadata when present."""
    doc = Document(
        content="test content",
        type=DocumentType.POST,
        metadata={"slug": "my-custom-slug"},
    )
    assert doc.slug == "my-custom-slug"
