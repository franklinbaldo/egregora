
import uuid
import pytest
from pydantic import ValidationError

from egregora_v3.core.types import Document, DocumentType





def test_slug_as_id():
    """A provided slug should be used as the ID."""
    doc = Document(content="Content", doc_type=DocumentType.POST, title="Test", slug="my-post")
    assert doc.id == "my-post"
    assert doc.internal_metadata.get("slug") == "my-post"


def test_slug_derived_from_title():
    """If no slug is provided, it should be derived from the title."""
    doc = Document(content="Content", doc_type=DocumentType.POST, title="My Awesome Post")
    assert doc.id == "my-awesome-post"
    assert doc.internal_metadata.get("slug") == "my-awesome-post"




def test_error_on_empty_slug_and_title():
    """If slug and title are empty, a ValueError should be raised."""
    with pytest.raises(ValidationError):
        Document(content="Content", doc_type=DocumentType.POST, title="", slug="")
