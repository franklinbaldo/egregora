# RFC: Egregora V3 Data Model - Documents & Feeds

**Status:** Approved (with revisions)
**Context:** Egregora V3 Re-architecture
**Date:** 2025-11-28 (Updated: December 2025)

> **🔄 Revision Notice (December 2025)**
>
> This RFC has been updated to reflect lessons learned during planning:
> - **AtomPub complexity (Sections 8-8.5) is ABANDONED** - Too complex, replaced by ContentLibrary
> - **Atom data model (Sections 1-7) is APPROVED** - Entry/Document/Feed are core to V3
> - **Privacy assumptions revised** - V3 targets public/privacy-ready data
>
> Historical AtomPub sections preserved for reference but marked deprecated.

---

## 1. Context and Objective

In V3, Egregora adopts the **Atom protocol** (RFC 4287) as the conceptual foundation for input and output data. This eliminates arbitrary distinctions between "chat messages", "blog posts", and "files", treating everything as entries in a feed.

**Data Flow:**
- **Input:** Adapters convert any source (RSS, Chat, API) into `Feed` + `Entry`
- **Processing:** The cognitive engine processes these `Entry` objects
- **Output:** Egregora produces `Document` objects (specialized Entries)

**Design Goals:**
1. **Single output type** - Simplification through unification
2. **Atom compliance** - Easy integration with feed readers and external tools
3. **Format agnostic** - Publication works with MkDocs, JSON API, Hugo, etc.

**Key Difference from V2:**
V3 assumes data is **already privacy-ready or public**. Privacy is not a core concern - applications needing anonymization use a composable `PrivacyAdapter`.

---

## 2. Symmetry Principle

V3 follows a linear, symmetric flow:

> **Input Feed → Processing → Output Feed**

1. Egregora ingests external feeds → normalizes to `Feed` + `Entry`
2. Egregora "thinks" and generates artifacts (posts, notes, plans) → creates `Document` objects
3. Documents are aggregated into output feeds (e.g., `egregora:documents`)

**Axiom:** Everything that enters is Atom; everything that exits is Atom (enriched).

---

## 3. Data Model

### 3.1 Atom Base (Core Domain)

V3 defines pure Pydantic models mirroring the Atom specification (RFC 4287), without legacy prefixes.

```python
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

class Link(BaseModel):
    """Atom link element."""
    href: str
    rel: str | None = None        # e.g., "alternate", "enclosure", "self"
    type: str | None = None       # e.g., "text/html", "image/jpeg"
    hreflang: str | None = None
    title: str | None = None
    length: int | None = None

class Author(BaseModel):
    """Atom author/contributor."""
    name: str
    email: str | None = None
    uri: str | None = None

class Category(BaseModel):
    """Atom category/tag."""
    term: str                     # Tag or category
    scheme: str | None = None     # URI of taxonomy scheme
    label: str | None = None      # Human-readable label

class Source(BaseModel):
    """Atom source metadata (for aggregated entries)."""
    id: str | None = None
    title: str | None = None
    updated: datetime | None = None
    links: list[Link] = Field(default_factory=list)

class InReplyTo(BaseModel):
    """Atom Threading Extension (RFC 4685)."""
    ref: str                      # ID of parent entry
    href: str | None = None       # Link to parent entry
    type: str | None = None

class Entry(BaseModel):
    """Atom entry - base unit of content."""
    id: str                       # Stable unique ID (URI or UUID)
    title: str
    updated: datetime
    published: datetime | None = None

    links: list[Link] = Field(default_factory=list)
    authors: list[Author] = Field(default_factory=list)
    contributors: list[Author] = Field(default_factory=list)
    categories: list[Category] = Field(default_factory=list)

    summary: str | None = None    # Short text / teaser
    content: str | None = None    # Main body (Markdown/HTML)
    content_type: str | None = None # e.g., "text/markdown"

    source: Source | None = None

    # Threading (RFC 4685)
    in_reply_to: InReplyTo | None = None

    # Public Atom extensions (e.g., Media RSS)
    extensions: dict[str, Any] = Field(default_factory=dict)

    # Internal system metadata (not serialized to public Atom)
    internal_metadata: dict[str, Any] = Field(default_factory=dict)
```

### 3.2 Document: The Output Unit

`Document` is Egregora's specialization of `Entry`. It carries application-specific semantics.

```python
from enum import Enum

class DocumentType(str, Enum):
    """Document types in Egregora."""
    RECAP = "recap"           # Summaries of time windows
    NOTE = "note"             # Atomic notes or context annotations
    PLAN = "plan"             # Agent planning documents
    POST = "post"             # Complete articles for publication
    MEDIA = "media"           # Media metadata (binary in links[rel=enclosure])
    PROFILE = "profile"       # Author/participant profiles
    ENRICHMENT = "enrichment" # URL/media enrichment results

class DocumentStatus(str, Enum):
    """Publication status."""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class Document(Entry):
    """
    Artifact generated by Egregora.
    Inherits from Entry to ensure Atom compatibility.
    """
    doc_type: DocumentType
    status: DocumentStatus = DocumentStatus.DRAFT

    # RAG indexing policy
    searchable: bool = True

    # Suggested path for file-based OutputAdapters (MkDocs/Hugo)
    # e.g., "posts/2025/my-article"
    url_path: str | None = None
```

**Implementation Notes:**

1. **Inheritance:** Since `Document` is an `Entry`, any persistence or indexing function accepting `Entry` accepts `Document`.

2. **Content:** `content` should preferably be text (Markdown). Binaries (images, generated PDFs) should be referenced via `links` with `rel="enclosure"`, keeping the `Document` object lightweight.

3. **Metadata:**
   - `extensions`: Use for data that makes sense in a public RSS feed (e.g., geo coordinates, license)
   - `internal_metadata`: Use for Egregora control data (e.g., `tokens_used`, `model_version`, `source_window_id`)

4. **Semantic Identity:**
   - Posts/Media: ID = slug (human-readable, e.g., "my-first-post")
   - Profiles: ID = UUID or explicit ID (stable across renames)
   - Enrichments: ID = content hash (automatic deduplication)

---

## 4. Output Feeds (`documents_to_feed`)

To maintain symmetry, the final output of an execution cycle is not a loose list of files, but a `Feed` object.

```python
class Feed(BaseModel):
    """Atom feed container."""
    id: str
    title: str
    updated: datetime
    entries: list[Entry] = Field(default_factory=list)
    authors: list[Author] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    subtitle: str | None = None

def documents_to_feed(
    docs: list[Document],
    feed_id: str,
    title: str,
    *,
    authors: list[Author] | None = None,
) -> Feed:
    """Aggregate documents into a valid Atom Feed."""
    if not docs:
        updated = datetime.now(UTC)
    else:
        updated = max(doc.updated for doc in docs)

    return Feed(
        id=feed_id,
        title=title,
        updated=updated,
        authors=authors or [],
        entries=docs
    )
```

**Usage:**
This allows an `OutputAdapter` to receive a `Feed` and decide how to persist:
- **MkDocsAdapter:** Iterates over `feed.entries`, checks `url_path`, writes `.md` files
- **APIAdapter:** Returns the Feed JSON directly
- **AtomXMLAdapter:** Serializes the object to XML

---

## 5. Invariants

### 5.1 Entry / Document

- **Stable ID:** The `id` must be non-empty and ideally deterministic (e.g., UUIDv5 based on content or slug + date) to enable idempotent updates
- **Title:** Non-empty
- **Updated:** Required (UTC timezone)
- **Content Rule:** Must have `content` OR at least one `link` (for documents that are references only)

### 5.2 Document-Specific

- **Type:** `doc_type` is required
- **Status:** `status` is required (default DRAFT)
- **Searchable:** Defaults to `True` for RAG indexing

---

## 6. Interactions

### 6.1 Input Adapters

Input adapters are **ignorant about `Document`**. They produce only `Feed` containing `Entry` objects.

Example:
```python
class RSSAdapter(InputAdapter):
    def read_entries(self) -> Iterator[Entry]:
        # Parse RSS feed, yield Entry objects
        ...
```

### 6.2 Memory / RAG

The memory system indexes `Entry`. Since `Document` is an `Entry`, it's indexed natively, allowing Egregora to "remember" what it wrote in the past (self-reflection) without special code.

### 6.3 Output Adapters

Port signature:
```python
class OutputSink(Protocol):
    def publish(self, feed: Feed) -> None: ...
```

The adapter receives the complete feed. It can filter (e.g., publish only status=PUBLISHED) and decide the physical layout.

---

## 7. TDD Strategy

1. **Core Types:** Test instantiation and validation of `Entry` and `Document` (ensure required fields)
2. **Feed Generation:** Test `documents_to_feed` with empty list (should generate valid feed with current updated time) and populated list (updated = max(entries))
3. **Adapter Contract:** Create a FakeAdapter that consumes a Feed and verify it accesses the correct fields of `Document` (like `url_path`)
4. **Roundtrip:** Test Pydantic serialization/deserialization to ensure nothing is lost

---

## 8. Organization and Persistence

> **⚠️ DEPRECATED: AtomPub Sections (8-8.5)**
>
> The following sections describe an AtomPub-style organization (Service/Workspace/Collection) that was deemed **too complex** during implementation planning (December 2025).
>
> **Decision:** Use **ContentLibrary** pattern instead - a simpler facade with typed repositories.
>
> These sections are preserved for historical reference but should NOT be implemented as described.

### ~~8.1 Concepts: Workspace and Collection~~ (DEPRECATED)

<details>
<summary>Click to view deprecated AtomPub design (Historical reference only)</summary>

A **Workspace** represents a "logical space" for publication (e.g., main site, private diary, draft area).

A **Collection** represents a set of documents of the same "functional type" (e.g., blog posts, notes, media).

```python
from pydantic import BaseModel, Field
from typing import Protocol

class DocumentRepository(Protocol):
    def save(self, doc: Document) -> Document: ...
    def get(self, doc_id: str) -> Document | None: ...
    def list(self, *, doc_type: DocumentType | None = None) -> list[Document]: ...

class Collection(BaseModel):
    id: str                       # e.g., "posts", "journal", "media"
    title: str                    # e.g., "Blog Posts"
    accepts: list[DocumentType]   # e.g., [DocumentType.POST]

    # Backend that knows how to persist and list Documents in this collection
    repository: DocumentRepository

class Workspace(BaseModel):
    title: str                    # e.g., "Egregora Main Site"
    collections: list[Collection] = Field(default_factory=list)
```

**Rule:** Agents don't "guess" file paths or table names. They always talk to collections by ID ("posts", "journal", "media"), and the backend decides if it's MkDocs, SQL, S3, etc.

</details>

**Actual Implementation (ContentLibrary):**

```python
# egregora_v3/core/catalog.py
class ContentLibrary(BaseModel):
    """Simplified repository facade."""
    posts: DocumentRepository
    media: DocumentRepository
    profiles: DocumentRepository
    journal: DocumentRepository
    enrichments: DocumentRepository

    def save(self, doc: Document) -> None:
        """Route document to correct repository based on type."""
        repo = self._get_repo(doc.doc_type)
        repo.save(doc)
```

**Why Simpler:**
- Direct access: `library.posts.save(doc)` vs AtomPub's `service.find_collection("posts").repository.save(doc)`
- No discovery overhead (Service Document, workspace traversal)
- Type-safe via mypy/pyright
- Multi-workspace support can be added later via constructor: `ContentLibrary(workspace_id="public")`

### ~~8.2 Service Catalog~~ (DEPRECATED)

<details>
<summary>Click to view deprecated Service Document design (Historical reference only)</summary>

In AtomPub, the client does GET /service to discover collections. In Egregora V3, this would be exposed as an in-memory catalog:

```python
class Service(BaseModel):
    """
    Catalog of workspaces and collections.
    Conceptual equivalent to AtomPub's Service Document.
    """
    workspaces: list[Workspace] = Field(default_factory=list)

    def find_collection(self, collection_id: str) -> Collection | None:
        for ws in self.workspaces:
            for col in ws.collections:
                if col.id == collection_id:
                    return col
        return None
```

</details>

**Not Implemented:** ContentLibrary provides direct typed access instead.

### ~~8.3 CRUD Operations AtomPub-style~~ (DEPRECATED)

<details>
<summary>Click to view deprecated CRUD operations (Historical reference only)</summary>

In AtomPub, operations include POST (create entry), PUT (update), GET feed (list), etc. In V3, this would define a high-level API inspired by these verbs:

```python
class WorkspaceService(Protocol):
    def create_document(self, collection_id: str, doc: Document) -> Document: ...
    def update_document(self, doc_id: str, doc: Document) -> Document: ...
    def list_documents(
        self,
        collection_id: str,
        doc_type: DocumentType | None = None,
    ) -> list[Document]: ...
```

</details>

**Actual Implementation:** Repository pattern with protocol-based interfaces.

### ~~8.4 Media (Media Resources and Media Link Entries)~~ (DEPRECATED)

<details>
<summary>Click to view deprecated media handling (Historical reference only)</summary>

AtomPub defines how to handle binary media:
- Media Resource → the file itself (JPEG, PDF, etc.)
- Media Link Entry → an entry/Document describing the media, pointing to the file

In V3, this becomes a convention:
- Binary doesn't go in content (Entry.content is text)
- Binary goes to media backend (filesystem/S3), referenced by a Document of type MEDIA with link rel="enclosure"

Example API:

```python
class MediaStore(Protocol):
    def upload(self, data: bytes, mime_type: str) -> Link:
        """Upload binary and return Link with href/type/length filled."""

class WorkspaceServiceWithMedia(WorkspaceService, Protocol):
    def upload_media_document(
        self,
        collection_id: str,
        data: bytes,
        mime_type: str,
        title: str,
        alt_text: str | None = None,
    ) -> Document:
        """1. Upload binary via MediaStore
        2. Create Document(doc_type=MEDIA) with link rel="enclosure"
        3. Persist in configured collections"""
```

</details>

**Actual Implementation:** Media handling via ContentLibrary.media repository. Binaries stored separately, referenced via `Link` with `rel="enclosure"`.

### ~~8.5 Benefits~~ (DEPRECATED - refers to AtomPub)

<details>
<summary>Click to view deprecated benefits section (Historical reference only)</summary>

Adopting an "AtomPub-style" layer provides:

1. Explicit discovery: Agents don't need to know paths; just collection IDs
2. Data/blob separation: Everything textual/semantic is Document (Atom Entry), binaries treated as media, linked via rel="enclosure"
3. Native multi-workspace: Easy to have "Public Blog" and "Private Diary" workspaces using same primitives
4. Future evolution (server): If Egregora becomes an HTTP server, this layer works well with real AtomPub (Service Document, Collections, ETags, etc.) without heavy refactoring

</details>

**Actual Benefits (ContentLibrary):**
1. ✅ Simpler API - direct typed access
2. ✅ No discovery overhead - repositories known at compile time
3. ✅ Type-safe - mypy/pyright validation
4. ✅ Extensible - can add AtomPub HTTP layer on top later if needed

---

## Summary

**Approved for V3:**
- ✅ Atom data model (Entry, Document, Feed, Link, Author, Category)
- ✅ Symmetric data flow (Input Feed → Processing → Output Feed)
- ✅ Document as specialized Entry with Egregora semantics
- ✅ Semantic identity (slugs for posts/media, UUIDs for profiles)
- ✅ Threading support (RFC 4685)
- ✅ Media handling via `rel="enclosure"` links

**Simplified/Replaced:**
- ❌ AtomPub Service/Workspace/Collection → Use ContentLibrary instead
- ❌ Service Document discovery → Direct repository access
- ❌ Complex CRUD operations → Simple repository protocol

**V3 Targets:**
- Public data sources (RSS feeds, APIs, public archives)
- Data assumed privacy-ready (no built-in anonymization)
- Applications needing privacy use PrivacyAdapter wrapper

V3 uses Atom to model data, and uses ContentLibrary to organize where and how that data lives and is manipulated. This provides robust semantics for agents and internal organization without AtomPub's complexity.

---

**Status:** Living document
**Last Updated:** December 2025
**Next Review:** March 2026 (Phase 1 completion)
