# Egregora V3: The Atom-Centric Architecture

**Status:** APPROVED (2025-11-28)
**Architect:** Jules
**Goal:** Unify ingestion, storage, and publication under a single protocol.

## 1. The Core Philosophy: "Everything is an Entry"

In V2, we had a fractured data model:
- `Message` (DuckDB table)
- `Document` (Pydantic object)
- `Post` (Markdown file)

In V3, we adopt the **Atom Syndication Format (RFC 4287)** as our universal language.
Every piece of content—whether a WhatsApp message, a generated blog post, a user profile, or a system log—is an `Entry`.

```python
@dataclass
class Entry:
    id: str                  # Atom ID (URN/UUID)
    title: str               # Atom Title
    updated: datetime        # Atom Updated
    authors: List[Author]    # Atom Authors
    content: Content         # Atom Content
    links: List[Link]        # Atom Links (Enclosures, Relations)
    categories: List[Category] # Atom Categories (Tags)

    # Extensions (for domain-specific data)
    extensions: Dict[str, Any]
```

### The Unification
| V2 Concept | V3 Concept | Type |
| :--- | :--- | :--- |
| WhatsApp Message | `Entry` | `type="message"` |
| Blog Post | `Entry` | `type="post"` |
| Author Profile | `Entry` | `type="profile"` |
| System Log | `Entry` | `type="log"` |
| Enrichment | `Entry` | `type="enrichment"` |

## 2. The Single-Table Storage Strategy

Instead of maintaining separate tables (`messages`, `runs`, `embeddings`), we use a single **Wide Table** in DuckDB.

**Table:** `documents`

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary Key |
| `doc_type` | `ENUM` | 'message', 'post', 'profile', ... |
| `title` | `VARCHAR` | |
| `updated` | `TIMESTAMP` | |
| `author_id` | `UUID` | Foreign Key (Logical) |
| `content_body` | `VARCHAR` | Main text content |
| `content_type` | `VARCHAR` | 'text/plain', 'text/markdown' |
| `json_metadata` | `JSON` | Stores `extensions`, `links`, etc. |
| `vector` | `FLOAT[]` | Embedding (optional) |

**Benefits:**
1.  **Universal Search:** RAG queries run against *everything* (posts, chats, logs) without complex joins.
2.  **Simplified Writes:** One sink for all agents.
3.  **Schema Evolution:** JSON column allows flexibility without migrations.

## 3. The Functional Pipeline

The system is a transformation pipeline of `Entry` streams.

```mermaid
graph LR
    A[WhatsApp Adapter] -->|Stream[Entry]| B(Privacy Filter)
    B -->|Stream[Entry]| C{Enrichment Loop}
    C -->|Entry| D[DuckDB Store]
    D -->|Context| E[Writer Agent]
    E -->|Entry (Post)| F[Output Sink]
```

### Key Changes
1.  **Input Adapters:** Now emit `Entry` objects, not raw dicts.
2.  **Privacy Layer:** A distinct pipe that masks PII *before* it hits the store.
3.  **Output Sinks:** `OutputSink` protocol receives `Entry` objects and decides how to render them (e.g., `MkDocsAdapter` writes `.md` files).

## 4. Migration Roadmap

### Phase 1: Foundation (High Priority)
- [ ] Define `src/egregora/core/types.py` with `Entry` and `Document`.
- [ ] Implement `UNIFIED_SCHEMA` in `src/egregora/database/ir_schema.py`.

### Phase 2: Adaptation (Medium Priority)
- [ ] Refactor `WhatsAppAdapter` to yield `Entry`.
- [ ] Update `Writer` agent to consume/produce `Entry`.

### Phase 3: Cleanup (Low Priority)
- [ ] Remove V2 `IR_MESSAGE_SCHEMA`.
- [ ] Migrate existing DuckDB data.
