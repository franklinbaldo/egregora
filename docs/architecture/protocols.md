# Core Protocols

Egregora uses Protocol classes (PEP 544) to define interfaces without inheritance. This document describes all core protocols in the codebase.

## Table of Contents

- [URL Generation](#url-generation)
- [Input Adapters](#input-adapters)
- [Output Sink](#output-sink)
- [RAG Backend](#rag-backend)
- [Database Protocols](#database-protocols)

---

## URL Generation

### UrlContext

**Module:** `egregora.data_primitives.protocols`

Frozen dataclass providing context information for URL generation.

```python
@dataclass(frozen=True, slots=True)
class UrlContext:
    """Context information required when generating canonical URLs."""

    base_url: str = ""           # Base URL (e.g., "https://example.com")
    site_prefix: str = ""        # Site prefix (e.g., "/blog")
    base_path: Path | None = None  # Filesystem base path
    locale: str | None = None    # Locale for i18n (e.g., "en", "pt-BR")
```

**Usage:**
```python
ctx = UrlContext(
    base_url="https://mysite.com",
    site_prefix="/posts",
    base_path=Path("/output/docs"),
    locale="en"
)
```

### UrlConvention

**Module:** `egregora.data_primitives.protocols`

Protocol for deterministic URL generation strategies.

```python
class UrlConvention(Protocol):
    """Contract for deterministic URL generation strategies.

    Pure function pattern: same document → same URL
    No I/O, no side effects - just URL calculation.
    """

    @property
    def name(self) -> str:
        """Return a short identifier describing the convention."""
        ...

    @property
    def version(self) -> str:
        """Return a semantic version or timestamp string for compatibility checks."""
        ...

    def canonical_url(self, document: Document, ctx: UrlContext) -> str:
        """Calculate the canonical URL for ``document`` within ``ctx``."""
        ...
```

**Key Properties:**
- **Deterministic:** Same document always produces same URL
- **Pure:** No I/O operations, no side effects
- **Versioned:** `name` and `version` for compatibility tracking
- **Context-aware:** Uses `UrlContext` for environment-specific configuration

**Example Implementation:**
```python
class MkDocsUrlConvention:
    """MkDocs-compatible URL convention."""

    @property
    def name(self) -> str:
        return "mkdocs-standard"

    @property
    def version(self) -> str:
        return "v1.0"

    def canonical_url(self, document: Document, ctx: UrlContext) -> str:
        # Posts: /posts/{slug}/
        # Pages: /{slug}/
        if document.type == DocumentType.POST:
            path = f"/posts/{document.slug}/"
        else:
            path = f"/{document.slug}/"

        return f"{ctx.base_url}{ctx.site_prefix}{path}"
```

**Why This Matters:**
- **SEO:** Stable URLs across rebuilds prevent broken links
- **Testing:** Pure functions are easy to test
- **Flexibility:** Swap conventions without changing callers
- **Compatibility:** Version tracking enables gradual migration

---

## Input Adapters

### InputAdapter

**Module:** `egregora.input_adapters.base`

Abstract Base Class (ABC) for bringing data INTO the pipeline.

```python
class InputAdapter(ABC):
    """Abstract base class for all source adapters."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the human-readable name of this source."""
        ...

    @property
    @abstractmethod
    def source_identifier(self) -> str:
        """Return the unique identifier for this source."""
        ...

    @abstractmethod
    def parse(self, input_path: Path, *, timezone: str | None = None, **kwargs: Any) -> Table:
        """Parse the raw export and return an IR-compliant Ibis Table.

        Returns:
            Ibis Table conforming to IR_SCHEMA
        """
        ...
```

**Available Implementations:**
- `WhatsAppAdapter` - Parse WhatsApp chat exports

**Key Responsibilities:**
- Parse external format
- Convert to `IR_MESSAGE_SCHEMA`
- Handle privacy/anonymization at source
- Yield data as Ibis tables (not pandas)

---

## Output Sink

### OutputSink

**Module:** `egregora.data_primitives.protocols`

Protocol for runtime data persistence and retrieval.

```python
@runtime_checkable
class OutputSink(Protocol):
    """Runtime data plane for document persistence and retrieval."""

    def persist(self, document: Document) -> None:
        """Persist document to output format.

        Must be idempotent - repeated calls with same document should overwrite.
        """
        ...

    def list(self, doc_type: DocumentType | None = None) -> Iterator[DocumentMetadata]:
        """Iterate through available documents metadata efficiently."""
        ...

    def documents(self) -> Iterator[Document]:
        """Iterate over all documents in output format."""
        ...
```

**Available Implementations:**
- `MkDocsAdapter` - Generate MkDocs sites (Implements `OutputSink` and `SiteScaffolder`)

**Key Responsibilities:**
- Persist `Document` to target format
- Idempotent writes (overwrite on repeat)
- Efficient document listing via metadata

---

## RAG Backend

### RAGBackend

**Module:** `egregora.rag.backend`

Protocol for vector storage backends.

```python
class VectorStore(Protocol):  # formerly RAGBackend
    """Protocol for RAG vector storage backends."""

    def add(self, documents: Sequence[Document]) -> int:
        """Add documents to the store."""
        ...

    def query(self, request: RAGQueryRequest) -> RAGQueryResponse:
        """Execute vector search in the knowledge base."""
        ...

    def delete(self, document_ids: list[str]) -> int:
        """Delete documents from the store."""
        ...
```

**Available Implementations:**
- `LanceDBRAGBackend` - LanceDB vector storage (current)

---

## Database Protocols

### Storage Protocols

**Module:** `egregora.database.protocols`

Protocols for database storage and retrieval.

```python
class TableStorage(Protocol):
    """Protocol for table storage operations."""

    def write_table(
        self,
        table: Table,
        name: str,
        *,
        checkpoint: bool = False
    ) -> None:
        """Write Ibis table to storage."""
        ...

    def read_table(self, name: str) -> Table:
        """Read Ibis table from storage."""
        ...

    def table_exists(self, name: str) -> bool:
        """Check if table exists."""
        ...
```

---

## Best Practices

### Protocol Design

1. **Keep protocols small** - Single Responsibility Principle
2. **Use `@runtime_checkable`** - Enable `isinstance()` checks
3. **Document return types** - Protocols are contracts
4. **Avoid concrete dependencies** - Depend on abstractions

### Implementation Guidelines

1. **Pure functions when possible** - UrlConvention example
2. **Idempotent operations** - OutputSink.persist()
3. **Lazy iteration** - Use `Iterator` not `list`

---

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Quick reference and key patterns
- [Architecture Overview](../guide/architecture.md) - System architecture
- [RAG Architecture](../api/knowledge/rag.md) - RAG implementation details
