# URL Convention System

## Overview

The **URL Convention** is the **single source of truth** for canonical URLs in the generated site. It defines how documents are addressed and referenced throughout the system, independent of how they are physically stored.

**Key Distinction:**
- **URL Convention:** Generates canonical URLs for the site (e.g., `/profiles/abc123`)
- **Adapter Implementation:** Decides how to persist/serve those URLs (filesystem, database, API, etc.)

For Static Site Generators (SSG) like MkDocs, URLs map to filesystem paths. But other adapters (e.g., database + FastAPI) could serve the same URLs without any files.

## Architecture

### Core Components

1. **`UrlConvention`** (Protocol/Interface)
   - Defines the contract for canonical URL generation
   - Location: `src/egregora/data_primitives/protocols.py`

2. **`StandardUrlConvention`** (Implementation)
   - Concrete implementation of URL generation rules
   - Generates URLs like `/profiles/{uuid}`, `/posts/{slug}`, etc.
   - Location: `src/egregora/output_adapters/conventions.py`

3. **Output Adapter** (Implementation-Specific)
   - Uses URL convention to get canonical URLs
   - Decides how to persist/serve documents at those URLs
   - **MkDocs:** Translates URLs to filesystem paths
   - **Database:** Could insert into DB with URL as identifier
   - **API:** Could register URL routes

### Document Persistence Flow

```
┌──────────────┐
│   Document   │
│   Object     │
└──────┬───────┘
       │
       ↓
┌──────────────────────────────────────────────────────┐
│  adapter.persist(document)                           │
└──────┬───────────────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────────────┐
│  url = convention.canonical_url(doc, context)        │
│                                                       │
│  Result: /profiles/d65bbd29-dccb-55bb-a839...        │
│                                                       │
│  ✓ This URL is used across the entire site:         │
│    - Navigation links                                │
│    - Cross-references                                │
│    - Template rendering                              │
│    - Writer agent output                             │
└──────┬───────────────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────────────┐
│  Adapter-Specific Persistence                        │
│                                                       │
│  SSG (MkDocs):                                       │
│    path = _url_to_path(url)                          │
│    → profiles/d65bbd29-dccb-55bb-a839....md         │
│    write_file(path, content)                         │
│                                                       │
│  Database:                                           │
│    db.insert(url=url, content=content, ...)          │
│                                                       │
│  API:                                                │
│    register_route(url, handler)                      │
└──────────────────────────────────────────────────────┘
```

## URL Convention Rules by Document Type

These are the **canonical URLs** used across the site, regardless of adapter implementation.

### PROFILE Documents

**Metadata Required:** `uuid` (author's UUID)

**Canonical URL:** `/profiles/{uuid}`

**Example:**
```python
Document(
    content="Profile content...",
    type=DocumentType.PROFILE,
    metadata={"uuid": "d65bbd29-dccb-55bb-a839-bed92ffe262b"}
)
```

**Generated URL:** `/profiles/d65bbd29-dccb-55bb-a839-bed92ffe262b`

**Adapter-Specific Storage:**
- **MkDocs:** `docs/profiles/d65bbd29-dccb-55bb-a839-bed92ffe262b.md`
- **Database:** `profiles` table with `url` column
- **API:** `GET /profiles/d65bbd29-dccb-55bb-a839-bed92ffe262b`

**Key Rules:**
- Uses **full UUID** from metadata (not truncated)
- No date prefix in URL
- URL is stable across regenerations

### POST Documents

**Metadata Required:** `slug`, `date`

**Canonical URL:** `/posts/{slug}`

**Example:**
```python
Document(
    content="Post content...",
    type=DocumentType.POST,
    metadata={
        "slug": "my-blog- post",
        "date": "2025-03-15"
    }
)
```

**Generated URL:** `/posts/my-blog-post`

**Adapter-Specific Storage:**
- **MkDocs:** `docs/blog/posts/2025-03-15-my-blog-post.md` (date in filename)
- **Database:** `posts` table with `url`, `date`, `slug` columns
- **API:** `GET /posts/my-blog-post` (date in metadata)

**Key Rules:**
- URL uses slug only (clean URLs)
- Slug is normalized (lowercase, hyphens)
- Date stored in metadata, not URL (for Jekyll/MkDocs compat)

### JOURNAL Documents

**Metadata Required:** `window_label` or `slug`

**Canonical URL:** `/journal/{safe_label}`

**Example:**
```python
Document(
    content="Journal entry...",
    type=DocumentType.JOURNAL,
    metadata={"window_label": "2025-03-15_08:00-12:00"}
)
```

**Generated URL:** `/journal/2025-03-15-08-00-12-00`

**Key Rules:**
- Label is slugified (special characters converted to hyphens)
- Represents time windows or agent memory snapshots

### MEDIA Documents

**Metadata Required:** `filename`, `media_hash`

**Canonical URL:** `/media/{type}/{identifier}.{ext}`

**Example:**
```python
Document(
    content=b"...",  # binary data
    type=DocumentType.MEDIA,
    metadata={
        "filename": "photo.jpg",
        "media_hash": "abc123"
    }
)
```

**Generated URL:** `/media/images/abc123.jpg`

**Key Rules:**
- Hash-based naming prevents collisions
- Preserves file extension
- Organized by media type (images/, videos/, etc.)

### ENRICHMENT_MEDIA Documents

**Metadata Required:** `parent_id`, `parent_slug`

**Canonical URL:** `/media/{type}/{parent_slug}`

**Example:**
```python
Document(
    content="Enrichment markdown...",
    type=DocumentType.ENRICHMENT_MEDIA,
    metadata={
        "parent_id": "abc123",
        "parent_slug": "vacation-photo"
    }
)
```

**Generated URL:** `/media/images/vacation-photo` (matches `/media/images/vacation-photo.jpg`)

**Key Rules:**
- Enrichment documents describe media files
- URL pattern aligns with paired media file

### ENRICHMENT_URL Documents

**Canonical URL:** Variable (uses `suggested_path` if available)

**Example:**
```python
Document(
    content="URL enrichment...",
    type=DocumentType.ENRICHMENT_URL,
    suggested_path="media/urls/article-abc123"
)
```

**Generated URL:** `/media/urls/article-abc123/`

**Key Rules:**
- Often uses `suggested_path` for flexibility
- Falls back to hash-based naming if no suggested_path

## Why This Matters

### 1. **Single Source of Truth for URLs**

The URL convention is the **only** authority for canonical URLs:
- How documents are addressed in the site
- How documents are referenced across templates
- How links are generated

**What it does NOT dictate:**
- Physical storage location (adapter-specific)
- Storage format (files, DB, API, etc.)
- Implementation details

### 2. **Adapter Independence**

The same URL can be served by different adapters:

```python
url = "/profiles/abc123"  # From URL convention

# MkDocs adapter:
path = "docs/profiles/abc123.md"
write_file(path, content)
serve_from_filesystem(url, path)

# Database adapter:
db.profiles.insert(url=url, content=content)
serve_from_db(url)

# API adapter:
@app.get("/profiles/{uuid}")
async def get_profile(uuid: str):
    return fetch_from_cache(f"/profiles/{uuid}")
```

### 3. **Consistency Across References**

All parts of the system use the **same canonical URL**:
- Writer agent: `[Profile](/profiles/abc123)`
- Template rendering: `<a href="/profiles/abc123">`
- Navigation menus: `{url: "/profiles/abc123"}`
- Internal cross-references: `/profiles/abc123`

This ensures **no broken links** regardless of adapter.

### 4. **Prevents Duplicates**

The duplicate profile files issue occurred because:
- ❌ Legacy code bypassed URL convention and manually created files
- ✅ Modern code uses URL convention → adapter persistence

With a single URL source, duplicates are impossible.

## Implementation: URL Generation

### conventions.py

```python
def canonical_url(self, document: Document, ctx: UrlContext) -> str:
    """Generate canonical URL for the generated site.

    Returns URL like /profiles/abc123, NOT filesystem paths.
    How the adapter serves this URL is implementation-specific.
    """

    if document.type == DocumentType.PROFILE:
        # Extract full UUID from metadata
        author_uuid = document.metadata.get("uuid") or document.metadata.get("author_uuid")
        return self._join(ctx, self.routes.profiles_prefix, author_uuid)
        # Result: /profiles/d65bbd29-dccb-55bb-a839-bed92ffe262b

    elif document.type == DocumentType.POST:
        # Use slug from metadata
        slug = document.metadata.get("slug")
        return self._join(ctx, self.routes.posts_prefix, slug)
        # Result: /posts/my-blog-post

    # ... other types
```

## Implementation: MkDocs Adapter (Filesystem)

### adapter.py

This is **MkDocs-specific** - other adapters would implement differently.

```python
def _url_to_path(self, url: str, document: Document) -> Path:
    """Convert canonical URL to filesystem path (MkDocs-specific).

    This translation is unique to SSG adapters. Database adapters
    wouldn't need this - they'd use the URL as-is for lookups.
    """
    url_path = url.strip("/")

    # Document-type-specific path resolution
    resolver = self._path_resolvers.get(document.type)
    return resolver(url_path)

def _resolve_profile_path(self, url_path: str) -> Path:
    """/profiles/{uuid} → docs/profiles/{uuid}.md (MkDocs-specific)"""
    uuid = url_path.split('/')[-1]
    return self.profiles_dir / f"{uuid}.md"

def _resolve_post_path(self, url_path: str) -> Path:
    """/posts/{slug} → docs/blog/posts/{date}-{slug}.md (MkDocs-specific)

    MkDocs/Jekyll convention: include date in filename for sorting.
    The URL stays clean (/posts/slug), but file has date prefix.
    """
    slug = url_path.split('/')[-1]
    date = self._extract_date_from_document(...)
    return self.posts_dir / f"{date}-{slug}.md"
```

## Anti-Patterns to Avoid

### ❌ Don't Bypass persist()

```python
# ❌ WRONG - Manual file/DB write
profiles_dir = Path("docs/profiles")
profile_path = profiles_dir / f"{author_uuid}.md"
profile_path.write_text(content)
```

**Why it's wrong:**
- Bypasses URL convention (no canonical URL generated)
- May use wrong path format
- Breaks link consistency across site
- Not tracked in adapter's index

### ❌ Don't Assume Storage Format

```python
# ❌ WRONG - Hardcoded filesystem assumptions
post_path = f"posts/{slug}.md"  # Assumes files exist!
```

**Why it's wrong:**
- Assumes SSG adapter (might be database)
- Path format is adapter-specific (MkDocs adds date prefix)
- Fragile to adapter changes

### ❌ Don't Manually Construct URLs

```python
# ❌ WRONG - Manual URL construction
profile_url = f"/profiles/{author_uuid[:8]}"  # Wrong format!
```

**Why it's wrong:**
- May not match canonical URL (short vs full UUID)
- Leads to broken links
- Inconsistent with URL convention

### ✅ Always Use URL Convention

```python
# ✅ CORRECT - Let URL convention generate canonical URL
doc = Document(
    content=content,
    type=DocumentType.PROFILE,
    metadata={"uuid": full_author_uuid}
)
adapter.persist(doc)

# Get canonical URL if needed:
url = adapter.url_convention.canonical_url(doc, adapter._ctx)
# Result: /profiles/d65bbd29-dccb-55bb-a839-bed92ffe262b

# Use this URL in links, templates, etc.
# How the adapter serves it (files/DB/API) doesn't matter
```

## Testing URL Conventions

### Unit Tests Should Verify

1. **Canonical URL generation** for each document type
2. **URL stability** (same metadata → same URL)
3. **URL format** matches expected patterns
4. **Metadata extraction** uses correct fields
5. **Edge cases** (missing metadata, special characters, etc.)

**Do NOT test:** Adapter-specific storage paths (those are adapter tests)

### Example Test

```python
def test_profile_url_uses_full_uuid():
    """Profile URLs must use full UUID, not truncated version."""
    full_uuid = "d65bbd29-dccb-55bb-a839-bed92ffe262b"

    doc = Document(
        content="Profile content",
        type=DocumentType.PROFILE,
        metadata={"uuid": full_uuid}
    )

    convention = StandardUrlConvention()
    ctx = UrlContext(base_url="", site_prefix="", base_path=Path("."))
    url = convention.canonical_url(doc, ctx)

    assert url == f"/profiles/{full_uuid}"
    # URL uses full UUID - how it's stored is adapter's concern
```

## Summary

**Remember:**
1. URL convention generates **canonical URLs for the site**
2. Adapters decide **how to persist/serve** those URLs
3. Same URL can be served by files (SSG), database, API, etc.
4. All documents **must** flow through `persist()` to get canonical URLs
5. Never bypass URL convention with manual storage code
6. Document metadata drives URL generation
7. Each document type has specific URL patterns

**When designing:**
- Think: "What URL should this document have in the site?"
- Don't think: "Where should I save this file?"

**When in doubt:** Check `StandardUrlConvention.canonical_url()` to see how your document type generates URLs.
