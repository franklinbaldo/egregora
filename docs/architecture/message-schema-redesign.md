# Message Schema Redesign: Minimal Document + Ibis Tables

**Status**: DRAFT
**Created**: 2025-01-15
**Purpose**: Resolve schema validation mismatch + establish clean abstraction

---

## Problem Statement

**Current Issue**: Pipeline validation expects `IR_MESSAGE_SCHEMA` (15 columns) but adapters produce `CONVERSATION_SCHEMA` (7 columns), causing 100% pipeline failure.

**Root Cause**: Over-engineered enterprise schema (IR) doesn't match Egregora's actual needs (personal privacy tool).

**Goal**: Design minimal, pragmatic schema that:
1. ✅ Solves the validation mismatch
2. ✅ Supports multiple sources (WhatsApp, Slack, Discord)
3. ✅ Maximizes Ibis usage (functional Table transformations)
4. ✅ Maintains privacy boundary
5. ✅ Uses generic field names (no `slack_thread_ts`)

---

## Design Philosophy

### 1. Minimal Core Schema

Messages have **only essential fields**. Everything else goes in `metadata` JSON.

```python
from typing import TypedDict, NotRequired, Any, Literal
from datetime import datetime

ProviderType = Literal["whatsapp", "slack", "discord", "email", "teams"]

class MessageDocument(TypedDict):
    """Minimal message schema - works for any conversational source."""

    # Identity
    message_id: str              # UUID5 deterministic ID

    # Source (two-level hierarchy)
    provider_type: ProviderType  # Platform: "whatsapp", "slack"
    provider_instance: str       # Specific: "family-chat", "#engineering"

    # Temporal
    timestamp: datetime          # UTC

    # Authorship (privacy boundary)
    author: str                  # Anonymized (8-char hex, NEVER raw)

    # Content
    content: str                 # Message text

    # Escape hatch (everything else)
    metadata: NotRequired[dict[str, Any]]
```

**Why minimal?**
- Provider-specific features go in `metadata` (threads, reactions, media)
- Schema never needs migration (adding features = adding to metadata)
- Adapters have flexibility without breaking contract

---

## 2. Ibis-First Pipeline

**Key Principle**: Maximize Ibis Table usage, minimize Python object conversion.

### Architecture Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ INPUT: Adapters produce Ibis Tables                             │
├─────────────────────────────────────────────────────────────────┤
│ WhatsApp ZIP → parse_zip() → Pandas DF → Ibis Table            │
│ Slack JSON   → parse_json() → Pandas DF → Ibis Table           │
│ Discord JSON → parse_json() → Pandas DF → Ibis Table           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PIPELINE: Functional Table → Table transformations              │
├─────────────────────────────────────────────────────────────────┤
│ validate_schema(table) → ensures standard schema                │
│ enrich_table(table) → adds LLM descriptions (Ibis UDFs)         │
│ window_table(table) → splits into windows (Ibis window funcs)  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ WRITER: Consumes Table, produces Documents                      │
├─────────────────────────────────────────────────────────────────┤
│ table.execute() → iterate rows → build prompt context          │
│ LLM → generates blog post markdown                              │
│ Document(type=POST, content="# My Post...") → output            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ OUTPUT: Documents written to disk                               │
├─────────────────────────────────────────────────────────────────┤
│ OutputAdapter.serve(document) → posts/2025-01-10-my-post.md    │
└─────────────────────────────────────────────────────────────────┘
```

### When to Use What

| Data Structure | Use When | Example |
|----------------|----------|---------|
| **Ibis Table** | Transformations, filtering, aggregations, windowing | `table.filter(table.content.contains("AI"))` |
| **Pandas DataFrame** | Vectorized operations in adapters, complex string ops | `df["author"] = df["author_raw"].map(author_map)` |
| **Python Dicts** | Individual row processing (rarely, only when needed) | Iterating rows to build LLM prompt |
| **Document** | Output representation (posts, profiles) | `Document(type=POST, content=markdown)` |

---

## 3. Standard Schema Definition

### Ibis Schema

```python
# src/egregora/database/schemas.py

import ibis.expr.datatypes as dt

MESSAGE_SCHEMA = ibis.schema({
    # Identity
    "message_id": dt.string,

    # Source
    "provider_type": dt.string,      # "whatsapp", "slack", "discord"
    "provider_instance": dt.string,  # "family-chat", "#engineering"

    # Temporal
    "timestamp": dt.Timestamp(timezone="UTC", scale=9),

    # Authorship
    "author": dt.string,  # Anonymized 8-char hex

    # Content
    "content": dt.string,

    # Metadata (JSON column)
    "metadata": dt.JSON(nullable=True),
})
```

### Schema Examples

**WhatsApp with media**:
```python
{
    "message_id": "abc-123-def",
    "provider_type": "whatsapp",
    "provider_instance": "family-chat",
    "timestamp": datetime(2025, 1, 10, 14, 30, tzinfo=UTC),
    "author": "7f3a9b2c",
    "content": "![Image](IMG-001.jpg)",
    "metadata": {
        "media": [{"filename": "IMG-001.jpg", "type": "image"}],
        "original_line": "10/01/2025, 14:30 - Alice: IMG-001.jpg (file attached)"
    }
}
```

**Slack with thread**:
```python
{
    "message_id": "xyz-789-abc",
    "provider_type": "slack",
    "provider_instance": "#engineering",
    "timestamp": datetime(2025, 1, 10, 15, 0, tzinfo=UTC),
    "author": "2b8c4e1a",
    "content": "Code review ready",
    "metadata": {
        "thread_ts": "1641827400.001200",
        "reactions": [{"emoji": "👍", "count": 3}]
    }
}
```

**Discord with attachments**:
```python
{
    "message_id": "qwe-456-rty",
    "provider_type": "discord",
    "provider_instance": "acme-corp/general",
    "timestamp": datetime(2025, 1, 10, 16, 0, tzinfo=UTC),
    "author": "4d9f1c2e",
    "content": "Check attachment",
    "metadata": {
        "attachments": [{"url": "https://cdn.discord.com/...", "filename": "doc.pdf"}]
    }
}
```

---

## 4. Privacy Architecture

### Anonymization Point

**Critical Rule**: `author_raw` (real names) NEVER leaves the adapter. Anonymization happens immediately during parsing.

```python
# INSIDE ADAPTER (ephemeral, never persisted)
class WhatsAppAdapter:
    def parse(self, zip_path: Path) -> Table:
        # 1. Parse to DataFrame
        df = parse_whatsapp_text(zip_path)
        # df has columns: timestamp, author_raw, content

        # 2. Anonymize IMMEDIATELY (vectorized)
        author_map = {name: anonymize(name) for name in df["author_raw"].unique()}
        df["author"] = df["author_raw"].map(author_map)

        # 3. DROP raw names before creating table
        df = df.drop(columns=["author_raw"])

        # 4. Return Ibis table (no raw names in it!)
        return ibis.memtable(df)
```

### Privacy Validation

```python
# src/egregora/privacy/validation.py

def validate_privacy(table: Table) -> None:
    """Ensure no raw names escaped anonymization."""

    schema = table.schema()

    # 1. Check forbidden columns don't exist
    forbidden_columns = ["author_raw", "author_name", "real_name"]
    if any(col in schema.names for col in forbidden_columns):
        raise PrivacyError(f"Raw name column found in table: {schema.names}")

    # 2. Verify 'author' column contains anonymized IDs
    authors = table.select("author").distinct().execute()["author"].tolist()
    for author in authors:
        if not re.match(r"^[0-9a-f]{8}$", author):
            raise PrivacyError(f"Author not anonymized: {author}")

    logger.info("✅ Privacy validation passed")
```

---

## Implementation Plan

### Phase 1: Define Schema (1 hour)

**File**: `src/egregora/database/schemas.py`

```python
"""Canonical message schema for all sources."""

import ibis.expr.datatypes as dt

# Minimal message schema (replaces IR_MESSAGE_SCHEMA + CONVERSATION_SCHEMA)
MESSAGE_SCHEMA = ibis.schema({
    "message_id": dt.string,
    "provider_type": dt.string,
    "provider_instance": dt.string,
    "timestamp": dt.Timestamp(timezone="UTC", scale=9),
    "author": dt.string,
    "content": dt.string,
    "metadata": dt.JSON(nullable=True),
})

def validate_schema(table: Table) -> None:
    """Validate table conforms to MESSAGE_SCHEMA."""
    actual = table.schema()
    expected = MESSAGE_SCHEMA

    # Check required columns exist
    required = {"message_id", "provider_type", "provider_instance",
                "timestamp", "author", "content"}
    actual_cols = set(actual.names)

    if not required.issubset(actual_cols):
        missing = required - actual_cols
        raise SchemaError(f"Missing required columns: {missing}")

    # Check types match
    for col in required:
        if actual[col] != expected[col]:
            raise SchemaError(
                f"Type mismatch for {col}: "
                f"expected {expected[col]}, got {actual[col]}"
            )
```

**Tests**: `tests/unit/test_message_schema.py`

```python
def test_message_schema_has_required_fields():
    """Test MESSAGE_SCHEMA has all required fields."""
    assert "message_id" in MESSAGE_SCHEMA.names
    assert "provider_type" in MESSAGE_SCHEMA.names
    assert "author" in MESSAGE_SCHEMA.names

def test_validate_schema_rejects_missing_columns():
    """Test validation fails on missing columns."""
    bad_table = ibis.memtable([{"message_id": "123", "content": "hi"}])
    with pytest.raises(SchemaError, match="Missing required columns"):
        validate_schema(bad_table)

def test_validate_schema_accepts_valid_table():
    """Test validation passes for valid table."""
    valid_table = ibis.memtable([{
        "message_id": "abc123",
        "provider_type": "whatsapp",
        "provider_instance": "test-group",
        "timestamp": datetime.now(UTC),
        "author": "7f3a9b2c",
        "content": "Hello",
    }], schema=MESSAGE_SCHEMA)
    validate_schema(valid_table)  # Should not raise
```

---

### Phase 2: Rewrite WhatsApp Adapter (2 hours)

**File**: `src/egregora/input_adapters/whatsapp.py`

```python
"""WhatsApp adapter - vectorized, Ibis-first."""

import pandas as pd
import ibis
from egregora.database.schemas import MESSAGE_SCHEMA

class WhatsAppAdapter(InputAdapter):

    def parse(self, input_path: Path, timezone: str = "UTC") -> Table:
        """Parse WhatsApp ZIP → Ibis Table (MESSAGE_SCHEMA).

        Uses vectorized Pandas operations for performance.
        """

        # 1. Discover group name
        group_name, chat_file = discover_chat_file(input_path)
        provider_instance = self._slugify(group_name)

        # 2. Parse to DataFrame (vectorized)
        df = self._parse_to_dataframe(input_path, chat_file, timezone)

        # 3. Add provider metadata (vectorized)
        df["provider_type"] = "whatsapp"
        df["provider_instance"] = provider_instance

        # 4. Anonymize authors (vectorized) + DROP author_raw
        df = self._anonymize_authors(df)

        # 5. Extract media to metadata (vectorized)
        df = self._extract_media_to_metadata(df)

        # 6. Generate deterministic IDs (vectorized)
        df = self._generate_message_ids(df)

        # 7. Ensure column order matches MESSAGE_SCHEMA
        df = df[["message_id", "provider_type", "provider_instance",
                 "timestamp", "author", "content", "metadata"]]

        # 8. Convert to Ibis Table
        table = ibis.memtable(df, schema=MESSAGE_SCHEMA)

        logger.info("✅ Parsed %d messages from %s", len(df), provider_instance)
        return table

    def _parse_to_dataframe(self, zip_path: Path, chat_file: str, tz: str) -> pd.DataFrame:
        """Parse WhatsApp text to DataFrame."""
        with zipfile.ZipFile(zip_path) as zf:
            with zf.open(chat_file) as f:
                lines = f.read().decode("utf-8").splitlines()

        # Parse lines
        rows = []
        for line in lines:
            parsed = parse_whatsapp_line(line)  # Existing parser
            if parsed:
                rows.append({
                    "timestamp": parsed.timestamp,
                    "author_raw": parsed.author,  # ⚠️ Temporary, will be dropped
                    "content": parsed.message,
                    "original_line": line,
                })

        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df

    def _anonymize_authors(self, df: pd.DataFrame) -> pd.DataFrame:
        """Anonymize authors using vectorized mapping."""
        # Build mapping
        unique_authors = df["author_raw"].unique()
        author_map = {name: anonymize_author(name) for name in unique_authors}

        # Apply vectorized
        df["author"] = df["author_raw"].map(author_map)

        # 🔒 CRITICAL: Drop raw names (privacy!)
        df = df.drop(columns=["author_raw"])

        return df

    def _extract_media_to_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract media references into metadata JSON column."""

        # Vectorized regex
        media_pattern = r"\b((?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)\b"
        df["media_files"] = df["content"].str.findall(media_pattern)

        # Build metadata JSON
        def build_metadata(row):
            meta = {}

            # Add media if present
            if row["media_files"]:
                meta["media"] = [
                    {
                        "filename": f,
                        "type": self._get_media_type(f)
                    }
                    for f in row["media_files"]
                ]

            # Add original line for debugging
            if "original_line" in row:
                meta["original_line"] = row["original_line"]

            return meta if meta else None

        df["metadata"] = df.apply(build_metadata, axis=1)

        # Convert media to markdown in content
        df["content"] = df.apply(
            lambda row: self._convert_media_to_markdown(
                row["content"],
                row["media_files"]
            ),
            axis=1
        )

        # Clean up temp columns
        df = df.drop(columns=["media_files", "original_line"])

        return df

    def _generate_message_ids(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate deterministic UUID5 message IDs."""

        def make_id(row):
            composite = (
                f"{row['provider_type']}:"
                f"{row['provider_instance']}:"
                f"{row['timestamp'].isoformat()}:"
                f"{row['author']}:"
                f"{row['content']}"
            )
            content_hash = hashlib.sha256(composite.encode()).hexdigest()
            return str(uuid5(NAMESPACE_MESSAGE, content_hash))

        df["message_id"] = df.apply(make_id, axis=1)
        return df

    @staticmethod
    def _slugify(name: str) -> str:
        """Convert group name to slug."""
        return name.lower().replace(" ", "-").replace("_", "-")

    @staticmethod
    def _get_media_type(filename: str) -> str:
        """Determine media type from extension."""
        ext = Path(filename).suffix.lower()
        if ext in [".jpg", ".png", ".gif", ".webp"]:
            return "image"
        elif ext in [".mp4", ".mov", ".avi"]:
            return "video"
        elif ext in [".mp3", ".ogg", ".opus"]:
            return "audio"
        else:
            return "document"
```

**Tests**: `tests/integration/test_whatsapp_adapter.py`

```python
def test_whatsapp_adapter_returns_valid_table(sample_whatsapp_zip):
    """Test adapter returns table conforming to MESSAGE_SCHEMA."""
    adapter = WhatsAppAdapter()
    table = adapter.parse(sample_whatsapp_zip)

    # Validate schema
    validate_schema(table)  # Should not raise

    # Check columns
    assert set(table.schema().names) >= {
        "message_id", "provider_type", "provider_instance",
        "timestamp", "author", "content"
    }

def test_whatsapp_adapter_anonymizes_authors(sample_whatsapp_zip):
    """Test no raw author names in output."""
    adapter = WhatsAppAdapter()
    table = adapter.parse(sample_whatsapp_zip)

    # Execute to DataFrame
    df = table.execute()

    # Check all authors are anonymized (8-char hex)
    assert all(re.match(r"^[0-9a-f]{8}$", author) for author in df["author"])

    # Check no raw name columns
    assert "author_raw" not in df.columns
    assert "author_name" not in df.columns

def test_whatsapp_adapter_sets_provider_fields(sample_whatsapp_zip):
    """Test provider_type and provider_instance are set."""
    adapter = WhatsAppAdapter()
    table = adapter.parse(sample_whatsapp_zip)

    df = table.execute()

    # All messages have same provider
    assert (df["provider_type"] == "whatsapp").all()
    assert df["provider_instance"].nunique() == 1  # Single group
    assert df["provider_instance"].iloc[0] != ""   # Not empty

def test_whatsapp_adapter_extracts_media_to_metadata(sample_whatsapp_zip_with_media):
    """Test media references go to metadata."""
    adapter = WhatsAppAdapter()
    table = adapter.parse(sample_whatsapp_zip_with_media)

    df = table.execute()

    # Find message with media
    msg_with_media = df[df["content"].str.contains("IMG-")].iloc[0]

    # Check metadata contains media info
    assert msg_with_media["metadata"] is not None
    assert "media" in msg_with_media["metadata"]
    assert len(msg_with_media["metadata"]["media"]) > 0
    assert msg_with_media["metadata"]["media"][0]["type"] == "image"
```

---

### Phase 3: Update Pipeline (1 hour)

**File**: `src/egregora/orchestration/write_pipeline.py`

```python
def _parse_and_validate(
    input_path: Path,
    adapter: InputAdapter,
    timezone: str | None = None,
) -> Table:
    """Parse input and validate schema.

    Replaces the old validate_ir_schema() with MESSAGE_SCHEMA validation.
    """
    logger.info("[bold cyan]📦 Parsing with adapter:[/] %s", adapter.source_name)

    # Parse to Ibis table
    messages_table = adapter.parse(input_path, timezone=timezone)

    # Validate MESSAGE_SCHEMA
    validate_schema(messages_table)

    # Validate privacy
    validate_privacy(messages_table)

    total_messages = messages_table.count().execute()
    logger.info("[green]✅ Parsed[/] %s messages", total_messages)

    # Log provider info
    providers = messages_table.select("provider_type", "provider_instance").distinct().execute()
    for _, row in providers.iterrows():
        logger.info(
            "[yellow]📱 Provider:[/] %s (%s)",
            row["provider_instance"],
            row["provider_type"]
        )

    return messages_table
```

**File**: `src/egregora/database/validation.py` (update)

```python
# Remove old IR_MESSAGE_SCHEMA validation
# Replace with MESSAGE_SCHEMA validation

from egregora.database.schemas import MESSAGE_SCHEMA, validate_schema

# Delete: validate_ir_schema() - no longer needed
# Delete: IR_MESSAGE_SCHEMA - using MESSAGE_SCHEMA instead
```

---

### Phase 4: Update Enrichment (1 hour)

**File**: `src/egregora/enrichment/batch.py`

```python
def enrich_table(table: Table, config: EgregoraConfig) -> Table:
    """Enrich messages with LLM descriptions (Ibis-native).

    Uses Ibis UDFs for vectorized enrichment.
    """

    # 1. Extract URLs from content (Ibis regex)
    urls_extracted = table.mutate(
        urls=table.content.re_findall(r"https?://[^\s]+")
    )

    # 2. Get unique URLs (avoid duplicate API calls)
    unique_urls_df = (
        urls_extracted
        .select("urls")
        .filter(urls_extracted.urls.length() > 0)
        .distinct()
        .execute()
    )

    all_urls = [url for urls in unique_urls_df["urls"] for url in urls]

    # 3. Batch describe URLs (single LLM call)
    url_descriptions = batch_describe_urls(all_urls, config)
    url_desc_map = dict(zip(all_urls, url_descriptions))

    # 4. Create Ibis UDF to add enrichments to metadata
    @ibis.udf.scalar.python
    def add_url_enrichment(content: str, metadata: dict | None) -> dict:
        """Add URL descriptions to metadata."""
        urls = re.findall(r"https?://[^\s]+", content)
        if not urls:
            return metadata or {}

        meta = metadata.copy() if metadata else {}
        meta["url_descriptions"] = [
            {"url": url, "description": url_desc_map[url]}
            for url in urls
            if url in url_desc_map
        ]
        return meta

    # 5. Apply enrichment (vectorized via Ibis UDF)
    enriched = table.mutate(
        metadata=add_url_enrichment(table.content, table.metadata)
    )

    return enriched
```

---

### Phase 5: Documentation Updates (30 min)

**Files to update**:
1. `README.md` - Change all `egregora process` → `egregora write`
2. `docs/getting-started/quickstart.md` - Update commands
3. `docs/guide/*.md` - Update examples
4. `CLAUDE.md` - Update architecture section

```bash
# Automated update
find . -name "*.md" -type f -exec sed -i 's/egregora process/egregora write/g' {} +
```

**New documentation**:
- `docs/architecture/message-schema.md` - Schema specification
- `docs/development/adapters.md` - How to write adapters

---

### Phase 6: Testing (1.5 hours)

**Test Coverage**:

1. **Schema validation** (`tests/unit/test_message_schema.py`)
   - Valid schema passes
   - Missing columns rejected
   - Wrong types rejected

2. **WhatsApp adapter** (`tests/integration/test_whatsapp_adapter.py`)
   - Returns valid MESSAGE_SCHEMA table
   - Anonymizes all authors
   - Sets provider fields correctly
   - Extracts media to metadata
   - Generates deterministic IDs

3. **Privacy validation** (`tests/unit/test_privacy_validation.py`)
   - Rejects tables with `author_raw` column
   - Rejects non-anonymized author IDs
   - Passes for valid anonymized data

4. **End-to-end** (`tests/e2e/test_write_pipeline.py`)
   - Full pipeline with real WhatsApp export
   - Generates blog posts successfully
   - No privacy leaks in output

---

## Migration Strategy

### Breaking Changes

This is a **clean break** (Alpha mindset):
- ❌ Remove: `IR_MESSAGE_SCHEMA` (15 columns)
- ❌ Remove: `CONVERSATION_SCHEMA` (7 columns)
- ✅ Add: `MESSAGE_SCHEMA` (7 columns, different structure)

### Steps

1. **Phase 1-2**: Implement new schema + WhatsApp adapter
2. **Phase 3**: Update pipeline to use MESSAGE_SCHEMA validation
3. **Phase 4**: Update enrichment to work with new schema
4. **Phase 5**: Update all documentation
5. **Phase 6**: Test suite passes
6. **Commit**: Single atomic commit with all changes

---

## Schema Comparison

| Old (IR_MESSAGE_SCHEMA) | New (MESSAGE_SCHEMA) | Change |
|-------------------------|----------------------|--------|
| `event_id` (UUID) | `message_id` (str) | Renamed, string not UUID |
| `tenant_id` | ❌ Removed | Not needed (single-user) |
| `source` | `provider_type` + `provider_instance` | Split into two levels |
| `thread_id` (UUID) | `metadata.thread_id` (any) | Moved to metadata |
| `msg_id` | ❌ Removed | Redundant with message_id |
| `ts` | `timestamp` | Renamed for clarity |
| `author_raw` | ❌ Never stored | Anonymized in adapter |
| `author_uuid` (UUID) | `author` (8-char hex) | Simpler format |
| `text` | `content` | Renamed for clarity |
| `media_url` | `metadata.media` | Moved to metadata |
| `media_type` | `metadata.media[].type` | Moved to metadata |
| `attrs` | ❌ Removed | Using metadata instead |
| `pii_flags` | ❌ Removed | Validation only, not stored |
| `created_at` | ❌ Removed | Not needed |
| `created_by_run` | ❌ Removed | Not needed |

**Summary**: 15 columns → 7 columns (53% reduction)

---

## Success Criteria

### ✅ Functional
- [ ] WhatsApp adapter parses exports successfully
- [ ] Pipeline validation passes with MESSAGE_SCHEMA
- [ ] No schema mismatch errors
- [ ] Blog posts generate end-to-end

### ✅ Privacy
- [ ] No `author_raw` anywhere except inside adapter (ephemeral)
- [ ] All `author` values are 8-char hex (anonymized)
- [ ] Privacy validation passes

### ✅ Code Quality
- [ ] All tests pass: `uv run pytest tests/`
- [ ] Pre-commit hooks pass: `uv run pre-commit run --all-files`
- [ ] No source-specific column names (validated in tests)

### ✅ Documentation
- [ ] All `egregora process` → `egregora write` (22 files)
- [ ] Architecture docs explain MESSAGE_SCHEMA
- [ ] Adapter guide shows how to implement new sources

---

## Timeline

**Total Effort**: ~7.5 hours

| Phase | Duration | Tasks |
|-------|----------|-------|
| 1. Schema | 1h | Define MESSAGE_SCHEMA, write validation |
| 2. Adapter | 2h | Rewrite WhatsApp adapter (vectorized) |
| 3. Pipeline | 1h | Update write_pipeline.py validation |
| 4. Enrichment | 1h | Update enrichment with Ibis UDFs |
| 5. Docs | 30m | Update all documentation |
| 6. Tests | 1.5h | Write comprehensive test suite |
| 7. Verification | 30m | End-to-end testing |

**Recommendation**: Implement in single day (6-8 hour session)

---

## Open Questions

1. **Metadata schema**: Should we validate metadata structure per provider?
   - **Decision**: No, keep flexible. Document conventions in adapter guide.

2. **Multiple sources in one collection**: How to handle mixed WhatsApp + Slack?
   - **Decision**: Tables can mix sources. Filter with `.filter(table.provider_type == "whatsapp")`

3. **Slack adapter**: Implement now or later?
   - **Decision**: Later. Focus on WhatsApp first, prove design works.

---

## References

- Current schema: `src/egregora/database/ir_schema.py`
- Current validation: `src/egregora/database/validation.py`
- Current adapter: `src/egregora/input_adapters/whatsapp.py`
- UX testing report: PR #770 `docs/ux-testing-2025-11-15.md`
