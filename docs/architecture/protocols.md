# Core Protocols

Egregora uses Protocol classes (PEP 544) to define interfaces without inheritance. This document describes all core protocols in the codebase.

## Table of Contents

- [URL Generation](#url-generation)
- [Input Adapters](#input-adapters)
- [Output Adapters](#output-adapters)
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

**Module:** `egregora.data_primitives.protocols`

Protocol for bringing data INTO the pipeline.

```python
@runtime_checkable
class InputAdapter(Protocol):
    """Adapter for reading external data sources and converting to IR."""

    def read(self) -> Iterator[Table]:
        """Read from source and yield Ibis tables conforming to IR_MESSAGE_SCHEMA.

        Returns:
            Iterator of Ibis tables with IR_MESSAGE_SCHEMA columns
        """
        ...

    @property
    def metadata(self) -> dict[str, Any]:
        """Return metadata about the input source."""
        ...
```

**Available Implementations:**
- `WhatsAppAdapter` - Parse WhatsApp chat exports
- `IperonTJROAdapter` - Brazilian judicial records API
- `SelfInputAdapter` - Re-ingest existing posts

**Key Responsibilities:**
- Parse external format
- Convert to `IR_MESSAGE_SCHEMA`
- Handle privacy/anonymization at source
- Yield data as Ibis tables (not pandas)

**Example:**
```python
class MyAdapter:
    def __init__(self, source_path: Path):
        self.source_path = source_path

    def read(self) -> Iterator[Table]:
        # Parse your format
        data = parse_my_format(self.source_path)

        # Convert to IR_MESSAGE_SCHEMA
        table = ibis.memtable(data).select(
            message_id=...,
            conversation_id=...,
            author_id=...,
            content=...,
            timestamp=...,
            # ... all IR_MESSAGE_SCHEMA columns
        )

        yield table

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "source_type": "my-format",
            "source_path": str(self.source_path),
            "version": "1.0"
        }
```

---

## Output Adapters

### OutputAdapter

**Module:** `egregora.data_primitives.protocols`

Protocol for taking data OUT of the pipeline.

```python
@runtime_checkable
class OutputAdapter(Protocol):
    """Adapter for persisting documents to external formats."""

    def persist(self, document: Document) -> None:
        """Persist document to output format.

        Must be idempotent - repeated calls with same document should overwrite.
        """
        ...

    def documents(self) -> Iterator[Document]:
        """Iterate over all documents in output format.

        Returns:
            Iterator for memory efficiency (not list)
        """
        ...
```

**Available Implementations:**
- `MkDocsAdapter` - Generate MkDocs sites
- `ParquetAdapter` - Export to Parquet format

**Key Responsibilities:**
- Convert `Document` to target format
- Idempotent writes (overwrite on repeat)
- Lazy document iteration
- Handle filesystem layout

**Example:**
```python
class MyOutputAdapter:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def persist(self, document: Document) -> None:
        # Calculate path
        path = self.output_dir / f"{document.slug}.html"

        # Convert Document to target format
        html = render_to_html(document)

        # Write (idempotent - overwrites)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html)

    def documents(self) -> Iterator[Document]:
        # Lazy iteration (not list)
        for path in self.output_dir.glob("*.html"):
            yield parse_html_to_document(path)
```

---

## RAG Backend

### RAGBackend

**Module:** `egregora.rag.backend`

Protocol for vector storage backends.

```python
class RAGBackend(Protocol):
    """Protocol for RAG vector storage backends."""

    async def index_documents(
        self,
        documents: Sequence[Document],
        *,
        embedding_fn: Callable[[Sequence[str], str], Awaitable[list[list[float]]]]
    ) -> int:
        """Index documents for retrieval.

        Args:
            documents: Documents to index
            embedding_fn: Async function to generate embeddings
                         Signature: (texts, task_type) -> embeddings

        Returns:
            Number of chunks indexed
        """
        ...

    async def search(
        self,
        request: RAGQueryRequest
    ) -> RAGQueryResponse:
        """Search indexed documents.

        Args:
            request: Search request with query text, top_k, filters

        Returns:
            Response with scored results
        """
        ...

    async def delete_all(self) -> None:
        """Delete all indexed documents."""
        ...
```

**Available Implementations:**
- `LanceDBRAGBackend` - LanceDB vector storage (current)

**Key Properties:**
- **Fully async:** All methods are async
- **Embedding injection:** Backend doesn't know about embedding models
- **Chunking:** Backend handles chunking internally
- **Task types:** Supports asymmetric embeddings (RETRIEVAL_DOCUMENT vs RETRIEVAL_QUERY)

**Example Usage:**
```python
from egregora.rag import LanceDBRAGBackend, RAGQueryRequest, index_documents

# Index documents
backend = LanceDBRAGBackend(db_path=Path(".egregora/lancedb"))
count = await index_documents([doc1, doc2, doc3])
print(f"Indexed {count} chunks")

# Search
request = RAGQueryRequest(
    text="how to use RAG",
    top_k=5,
    min_similarity=0.7
)
response = await backend.search(request)

for hit in response.hits:
    print(f"{hit.score:.2f}: {hit.text[:100]}")
```

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
2. **Idempotent operations** - OutputAdapter.persist()
3. **Lazy iteration** - Use `Iterator` not `list`
4. **Async by default** - RAGBackend example

### Testing Protocols

```python
# Test with mock implementation
class MockOutputAdapter:
    def __init__(self):
        self.documents_dict = {}

    def persist(self, document: Document) -> None:
        self.documents_dict[document.id] = document

    def documents(self) -> Iterator[Document]:
        yield from self.documents_dict.values()

# Verify protocol compliance
from egregora.data_primitives.protocols import OutputAdapter
assert isinstance(MockOutputAdapter(), OutputAdapter)
```

---

## Related Documentation

- [CLAUDE.md](../../CLAUDE.md) - Quick reference and key patterns
- [Architecture Overview](./README.md) - System architecture
- [RAG Architecture](./rag.md) - RAG implementation details
- [Pipeline Design](./pipeline.md) - Pipeline stages and transforms
