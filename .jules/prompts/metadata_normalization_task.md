# Task: Implement Structured DocumentMetadata Dataclass

## Objective
Create a well-defined `PublishableMetadata` dataclass with typed fields and sensible defaults, used consistently throughout the codebase for document publishing metadata.

---

## Approach: Test-Driven Development (TDD)

**CRITICAL:** You MUST follow TDD. Write tests FIRST, then implement.

---

## Architecture Decision

**Problem:** Currently `Document.metadata` is `dict[str, Any]` - no type safety, no defaults, inconsistent structure across document types.

**Solution:** Create a `PublishableMetadata` dataclass:

```python
@dataclass(frozen=True, slots=True)
class PublishableMetadata:
    """Structured metadata for publishable documents.
    
    Used consistently across all document types to ensure
    themes, plugins, and feeds can rely on these fields.
    """
    # Core identity
    title: str
    slug: str
    
    # Timestamps (ISO 8601 strings)
    date: str
    updated: str
    
    # Content metadata
    summary: str = ""
    tags: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    authors: tuple[str, ...] = ()
    
    # Publishing state
    draft: bool = False
    
    # Document identity
    doc_type: str = ""
    doc_id: str = ""
    
    # Provenance
    source_adapter: str = "unknown"
    source_window: str | None = None
    
    # Extension point for custom fields
    extra: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_document(cls, doc: Document) -> PublishableMetadata:
        """Create from Document, applying defaults for missing values."""
        ...
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for frontmatter serialization."""
        ...
```

**Why dataclass over TypedDict:**
- Default values built-in
- Type checking at runtime with `dacite` or similar
- IDE autocomplete works perfectly
- Frozen = immutable = safe
- Can have methods (`from_document`, `to_dict`)

**Why not modify Document.metadata type:**
- Breaking change for too many places
- Document is core, metadata is output-specific
- Gradual migration path

---

## Phase 1: Write Failing Tests First

### Test File: `tests/unit/metadata/test_publishable_metadata.py`

```python
# tests/unit/metadata/test_publishable_metadata.py

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from egregora.data_primitives.document import Document, DocumentType
from egregora.metadata.publishable import PublishableMetadata


class TestPublishableMetadataDefaults:
    """Tests for default values in PublishableMetadata."""

    def test_summary_defaults_to_empty_string(self) -> None:
        meta = PublishableMetadata(
            title="Test",
            slug="test",
            date="2025-01-15T10:00:00Z",
            updated="2025-01-15T10:00:00Z",
        )
        assert meta.summary == ""

    def test_tags_defaults_to_empty_tuple(self) -> None:
        meta = PublishableMetadata(
            title="Test",
            slug="test",
            date="2025-01-15T10:00:00Z",
            updated="2025-01-15T10:00:00Z",
        )
        assert meta.tags == ()
        assert isinstance(meta.tags, tuple)

    def test_draft_defaults_to_false(self) -> None:
        meta = PublishableMetadata(
            title="Test",
            slug="test",
            date="2025-01-15T10:00:00Z",
            updated="2025-01-15T10:00:00Z",
        )
        assert meta.draft is False


class TestPublishableMetadataFromDocument:
    """Tests for creating PublishableMetadata from Document."""

    @pytest.fixture
    def sample_document(self) -> Document:
        return Document(
            content="# Test Post",
            type=DocumentType.POST,
            metadata={
                "title": "My Post Title",
                "slug": "my-post",
                "tags": ["python", "testing"],
            },
            created_at=datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        )

    def test_from_document_extracts_existing_metadata(
        self, sample_document: Document
    ) -> None:
        meta = PublishableMetadata.from_document(sample_document)
        
        assert meta.title == "My Post Title"
        assert meta.slug == "my-post"
        assert meta.tags == ("python", "testing")

    def test_from_document_uses_created_at_for_date(
        self, sample_document: Document
    ) -> None:
        meta = PublishableMetadata.from_document(sample_document)
        
        assert meta.date == "2025-06-15T10:00:00+00:00"

    def test_from_document_defaults_title_if_missing(self) -> None:
        doc = Document(
            content="Content",
            type=DocumentType.POST,
            metadata={"slug": "test"},
        )
        
        meta = PublishableMetadata.from_document(doc)
        
        assert meta.title == "Untitled Post"

    def test_from_document_defaults_updated_to_date(self) -> None:
        doc = Document(
            content="Content",
            type=DocumentType.POST,
            metadata={"slug": "test"},
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        
        meta = PublishableMetadata.from_document(doc)
        
        assert meta.updated == meta.date

    def test_from_document_preserves_extra_fields(self) -> None:
        doc = Document(
            content="Content",
            type=DocumentType.POST,
            metadata={
                "slug": "test",
                "custom_field": "custom_value",
                "another_field": 123,
            },
        )
        
        meta = PublishableMetadata.from_document(doc)
        
        assert meta.extra["custom_field"] == "custom_value"
        assert meta.extra["another_field"] == 123

    @pytest.mark.parametrize("doc_type", list(DocumentType))
    def test_from_document_works_for_all_types(
        self, doc_type: DocumentType
    ) -> None:
        doc = Document(
            content="Content",
            type=doc_type,
            metadata={"slug": f"test-{doc_type.value}"},
        )
        
        meta = PublishableMetadata.from_document(doc)
        
        assert meta.doc_type == doc_type.value


class TestPublishableMetadataToDict:
    """Tests for serializing PublishableMetadata to dict."""

    def test_to_dict_includes_all_fields(self) -> None:
        meta = PublishableMetadata(
            title="Test",
            slug="test",
            date="2025-01-15T10:00:00Z",
            updated="2025-01-15T10:00:00Z",
            tags=("a", "b"),
            authors=("author-1",),
        )
        
        d = meta.to_dict()
        
        assert d["title"] == "Test"
        assert d["slug"] == "test"
        assert d["tags"] == ["a", "b"]  # Converts tuple to list
        assert d["authors"] == ["author-1"]

    def test_to_dict_merges_extra_fields(self) -> None:
        meta = PublishableMetadata(
            title="Test",
            slug="test",
            date="2025-01-15T10:00:00Z",
            updated="2025-01-15T10:00:00Z",
            extra={"custom": "value"},
        )
        
        d = meta.to_dict()
        
        assert d["custom"] == "value"

    def test_to_dict_omits_none_source_window(self) -> None:
        meta = PublishableMetadata(
            title="Test",
            slug="test",
            date="2025-01-15T10:00:00Z",
            updated="2025-01-15T10:00:00Z",
            source_window=None,
        )
        
        d = meta.to_dict()
        
        assert "source_window" not in d or d.get("source_window") is None


class TestPublishableMetadataImmutability:
    """Tests that PublishableMetadata is immutable."""

    def test_cannot_modify_fields(self) -> None:
        meta = PublishableMetadata(
            title="Test",
            slug="test",
            date="2025-01-15T10:00:00Z",
            updated="2025-01-15T10:00:00Z",
        )
        
        with pytest.raises(AttributeError):
            meta.title = "New Title"  # type: ignore
```

---

## Phase 2: Implement to Make Tests Pass

### Step 1: Create `PublishableMetadata` dataclass

**File:** `src/egregora/metadata/publishable.py`

```python
"""Structured metadata for publishable documents.

This module provides type-safe metadata with sensible defaults,
ensuring consistent structure across all document types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from egregora.data_primitives.document import Document, DocumentType

# Known fields that map to dataclass attributes
KNOWN_FIELDS = frozenset({
    "title", "slug", "date", "updated", "summary",
    "tags", "categories", "authors", "draft",
    "type", "doc_id", "source_adapter", "source_window",
})


def _get_fallback_title(doc_type: DocumentType) -> str:
    """Generate fallback title based on document type."""
    return f"Untitled {doc_type.value.capitalize()}"


@dataclass(frozen=True, slots=True)
class PublishableMetadata:
    """Structured metadata for publishable documents.
    
    Immutable dataclass with sensible defaults. Use `from_document()`
    to create from a Document instance, or construct directly.
    
    Fields are designed to support:
    - MkDocs frontmatter
    - RSS feeds
    - Sitemaps
    - Social cards
    """
    
    # Core identity (required)
    title: str
    slug: str
    
    # Timestamps (ISO 8601)
    date: str
    updated: str
    
    # Content metadata (with defaults)
    summary: str = ""
    tags: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    authors: tuple[str, ...] = ()
    
    # Publishing state
    draft: bool = False
    
    # Document identity
    doc_type: str = ""
    doc_id: str = ""
    
    # Provenance
    source_adapter: str = "unknown"
    source_window: str | None = None
    
    # Extension point
    extra: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_document(cls, doc: Document) -> PublishableMetadata:
        """Create PublishableMetadata from a Document.
        
        Extracts known fields from doc.metadata, applies defaults
        for missing values, and puts unknown fields into `extra`.
        """
        meta = doc.metadata
        
        # Extract or compute values
        title = meta.get("title") or _get_fallback_title(doc.type)
        slug = meta.get("slug") or doc.slug
        date = meta.get("date") or doc.created_at.isoformat()
        updated = meta.get("updated") or date
        
        # Convert lists to tuples for immutability
        tags = tuple(meta.get("tags") or [])
        categories = tuple(meta.get("categories") or [])
        authors = tuple(meta.get("authors") or [])
        
        # Collect extra fields
        extra = {k: v for k, v in meta.items() if k not in KNOWN_FIELDS}
        
        return cls(
            title=title,
            slug=slug,
            date=date,
            updated=updated,
            summary=meta.get("summary", ""),
            tags=tags,
            categories=categories,
            authors=authors,
            draft=bool(meta.get("draft", False)),
            doc_type=doc.type.value,
            doc_id=doc.document_id,
            source_adapter=meta.get("source_adapter", "unknown"),
            source_window=doc.source_window,
            extra=extra,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for frontmatter serialization.
        
        - Tuples are converted to lists
        - Extra fields are merged in
        - None values may be omitted
        """
        result: dict[str, Any] = {
            "title": self.title,
            "slug": self.slug,
            "date": self.date,
            "updated": self.updated,
            "summary": self.summary,
            "tags": list(self.tags),
            "categories": list(self.categories),
            "authors": list(self.authors),
            "draft": self.draft,
            "type": self.doc_type,
            "doc_id": self.doc_id,
            "source_adapter": self.source_adapter,
        }
        
        if self.source_window:
            result["source_window"] = self.source_window
        
        # Merge extra fields
        result.update(self.extra)
        
        return result
```

### Step 2: Update adapter to use PublishableMetadata

**File:** `src/egregora/output_adapters/mkdocs/adapter.py`

```python
from egregora.metadata.publishable import PublishableMetadata

def persist(self, document: Document) -> None:
    # Create structured metadata
    meta = PublishableMetadata.from_document(document)
    
    # Use meta.to_dict() when writing frontmatter
    ...
```

---

## Acceptance Criteria

- [ ] `PublishableMetadata` dataclass is frozen and slotted
- [ ] All tests pass
- [ ] `from_document()` handles all DocumentTypes
- [ ] `to_dict()` produces valid frontmatter dict
- [ ] Extra fields are preserved
- [ ] Tuples used for immutable sequences (tags, categories, authors)
- [ ] Ruff lint/format pass

---

## Files to Create/Modify

1. `src/egregora/metadata/publishable.py` - NEW dataclass
2. `src/egregora/output_adapters/mkdocs/adapter.py` - Use PublishableMetadata
3. `tests/unit/metadata/test_publishable_metadata.py` - NEW tests

---

## Do NOT

- Modify the core `Document` dataclass
- Use mutable default values (lists) - use tuples
- Forget to handle None values in metadata
- Skip immutability (frozen=True)
