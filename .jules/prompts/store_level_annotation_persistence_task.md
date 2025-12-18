# Task: Implement Store-Level Annotation Persistence

## Objective
Refactor annotation persistence to use a cleaner architecture where `AnnotationsStore` handles document persistence internally, removing duplicate persistence logic from agent call sites.

---

## Approach: Test-Driven Development (TDD)

**CRITICAL:** You MUST follow TDD. Write tests FIRST, then implement.

---

## Current Problem

Duplicate persistence logic in two places:
1. `src/egregora/agents/types.py` - `annotate()` method
2. `src/egregora/agents/writer_tools.py` - `annotate_conversation_impl()`

---

## Better Architecture: Store-Level Auto-Persist

Move persistence INTO the store:

```python
class AnnotationsStore:
    def __init__(self, db, output_sink: OutputSink | None = None):
        self.output_sink = output_sink
    
    def save_annotation(self, ...) -> Annotation:
        annotation = self._save_to_db(...)
        if self.output_sink:
            self.output_sink.persist(annotation.to_document())
        return annotation
```

---

## Phase 1: Write Failing Tests First

### Test File: `tests/unit/annotations/test_annotation_persistence.py`

```python
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from egregora.agents.shared.annotations import AnnotationStore, Annotation
from egregora.data_primitives.document import DocumentType


class TestAnnotationStorePersistence:

    @pytest.fixture
    def mock_output_sink(self):
        sink = MagicMock()
        sink.persist = MagicMock()
        return sink

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    def test_save_annotation_persists_document_when_sink_provided(
        self, mock_db, mock_output_sink
    ) -> None:
        store = AnnotationStore(db=mock_db, output_sink=mock_output_sink)
        
        annotation = store.save_annotation(
            parent_id="msg-123",
            parent_type="message",
            commentary="Important observation.",
        )
        
        mock_output_sink.persist.assert_called_once()
        persisted_doc = mock_output_sink.persist.call_args[0][0]
        assert persisted_doc.type == DocumentType.ANNOTATION

    def test_save_annotation_works_without_sink(self, mock_db) -> None:
        store = AnnotationStore(db=mock_db, output_sink=None)
        
        annotation = store.save_annotation(
            parent_id="msg-456",
            parent_type="message",
            commentary="Another observation.",
        )
        
        assert annotation is not None

    def test_persist_failure_does_not_fail_save(
        self, mock_db, mock_output_sink
    ) -> None:
        mock_output_sink.persist.side_effect = IOError("Disk full")
        store = AnnotationStore(db=mock_db, output_sink=mock_output_sink)
        
        annotation = store.save_annotation(
            parent_id="msg-789",
            parent_type="message",
            commentary="Test observation.",
        )
        
        assert annotation is not None


class TestAnnotationDocumentConversion:

    def test_to_document_creates_annotation_type(self) -> None:
        annotation = Annotation(
            id=42,
            parent_id="msg-123",
            parent_type="message",
            author="egregora",
            commentary="Test commentary",
            created_at=datetime.now(timezone.utc),
        )
        
        doc = annotation.to_document()
        
        assert doc.type == DocumentType.ANNOTATION
        assert doc.metadata["annotation_id"] == "42"
```

---

## Phase 2: Implement to Make Tests Pass

### Step 1: Update `AnnotationStore.__init__`

**File:** `src/egregora/agents/shared/annotations/__init__.py`

```python
from egregora.data_primitives.protocols import OutputSink

class AnnotationStore:
    def __init__(self, db: Any, output_sink: OutputSink | None = None) -> None:
        self.db = db
        self.output_sink = output_sink
        self._ensure_table()
```

### Step 2: Update `save_annotation`

```python
def save_annotation(self, parent_id: str, parent_type: str, commentary: str, author: str = "egregora") -> Annotation:
    annotation = self._insert_annotation(parent_id=parent_id, parent_type=parent_type, commentary=commentary, author=author)
    
    if self.output_sink:
        try:
            doc = annotation.to_document()
            self.output_sink.persist(doc)
        except Exception as e:
            logger.warning("Failed to persist annotation: %s", e)
    
    return annotation
```

### Step 3: Remove duplicate persist calls

**File:** `src/egregora/agents/types.py` - Remove manual persist
**File:** `src/egregora/agents/writer_tools.py` - Remove manual persist

### Step 4: Keep URL convention and adapter changes

Keep from PR #1315:
- `conventions.py` - `_format_annotation_url()`
- `adapter.py` - `_write_annotation_doc()`, `_resolve_document_path()` for ANNOTATION

---

## Acceptance Criteria

- [ ] All tests pass
- [ ] `AnnotationStore.__init__` accepts optional `output_sink`
- [ ] `save_annotation` persists when sink available
- [ ] Agent code does NOT call `persist()` directly
- [ ] Ruff lint/format pass

## Files to Modify

1. `src/egregora/agents/shared/annotations/__init__.py`
2. `src/egregora/agents/types.py`
3. `src/egregora/agents/writer_tools.py`
4. `src/egregora/output_adapters/conventions.py` (keep from PR #1315)
5. `src/egregora/output_adapters/mkdocs/adapter.py` (keep from PR #1315)
6. `tests/unit/annotations/test_annotation_persistence.py` (NEW)
