# Schema Migration Guide

## PRs 539-543: DuckDB SQL Optimizations and Schema Improvements

This document describes schema changes introduced in the merge of PRs 539-543 and how to handle migrations.

### Schema Changes

#### 1. RAG_CHUNKS_METADATA_SCHEMA

**Added Fields:**
- `row_count` (int64, NOT NULL) - Physical row count from Parquet metadata at indexing time
- Modified `checksum` from NOT NULL to nullable

**Migration:**
```sql
-- For existing databases, add the new column with a default value
ALTER TABLE rag_chunks_metadata ADD COLUMN row_count BIGINT DEFAULT 0;
ALTER TABLE rag_chunks_metadata ALTER COLUMN checksum DROP NOT NULL;

-- Optionally backfill row_count by reading Parquet files
-- (code in src/egregora/knowledge/rag/store.py handles this automatically on next write)
```

**Backward Compatibility:** The migration helper in `VectorStore._migrate_index_meta_table()` automatically adds missing columns.

#### 2. RAG_INDEX_META_SCHEMA

**Added Fields:**
- `threshold` (int64, NOT NULL) - Threshold for ANN vs exact search
- `nlist` (int32, nullable) - Number of lists for ANN implementations
- `embedding_dim` (int32, nullable) - Embedding dimensionality for consistency checks
- **`created_at` (timestamp, NOT NULL) - Preserved from original schema**
- `updated_at` (timestamp, nullable) - Last update timestamp

**IMPORTANT:** We **kept** `created_at` in addition to adding `updated_at` to preserve provenance.

**Migration:**
```sql
-- Existing tables will have created_at; we add the new fields
ALTER TABLE rag_index_meta ADD COLUMN threshold BIGINT DEFAULT 100;
ALTER TABLE rag_index_meta ADD COLUMN nlist INTEGER;
ALTER TABLE rag_index_meta ADD COLUMN embedding_dim INTEGER;
ALTER TABLE rag_index_meta ADD COLUMN updated_at TIMESTAMP;

-- Backfill updated_at from created_at if desired
UPDATE rag_index_meta SET updated_at = created_at WHERE updated_at IS NULL;
```

**Backward Compatibility:** The migration helper in `VectorStore._migrate_index_meta_table()` automatically adds missing columns.

#### 3. ANNOTATIONS_SCHEMA

**Changed:**
- ID generation now uses DuckDB sequences instead of MAX(id)+1
- Uses `INSERT ... RETURNING` for atomic ID retrieval

**Migration:**
```sql
-- Create sequence for existing table
CREATE SEQUENCE IF NOT EXISTS annotations_id_seq START 1;

-- Set default to use sequence
ALTER TABLE annotations ALTER COLUMN id SET DEFAULT nextval('annotations_id_seq');

-- Sync sequence with existing max ID
-- (code in AnnotationStore._initialize() handles this automatically)
```

**Backward Compatibility:** Initialization code automatically detects MAX(id) and advances the sequence appropriately.

#### 4. ELO_RATINGS_SCHEMA

**Optimizations:**
- Changed to use set-based operations (anti-join INSERT, single CASE UPDATE)
- No schema changes, purely query optimization

**Migration:** None required - existing tables work as-is.

### Automatic Migration

All schema migrations are **automatically applied** when the application starts:

1. `database_schema.create_table_if_not_exists()` creates tables with new schema
2. `VectorStore._migrate_index_meta_table()` adds missing columns to existing RAG tables
3. `AnnotationStore._initialize()` creates sequences and syncs them with existing data

### Manual Migration (Optional)

If you want to inspect or manually control migration:

```python
import ibis
from egregora.data_primitives import database_schema
from egregora.knowledge.rag.store import VectorStore
from egregora.knowledge.annotations import AnnotationStore

# Connect to existing database
conn = ibis.duckdb.connect("path/to/your.db")

# Check current schema
print(conn.list_tables())
print(conn.sql("PRAGMA table_info('rag_index_meta')").execute())

# Migrations run automatically on instantiation
store = VectorStore(db_path="path/to/your.db")
annotation_store = AnnotationStore(db_path="path/to/your.db")
```

### Rollback

If you need to rollback to the previous schema:

```sql
-- Remove new columns (loses data in these columns!)
ALTER TABLE rag_chunks_metadata DROP COLUMN row_count;
ALTER TABLE rag_index_meta DROP COLUMN threshold;
ALTER TABLE rag_index_meta DROP COLUMN nlist;
ALTER TABLE rag_index_meta DROP COLUMN embedding_dim;
ALTER TABLE rag_index_meta DROP COLUMN updated_at;

-- Remove sequence
DROP SEQUENCE IF EXISTS annotations_id_seq;
ALTER TABLE annotations ALTER COLUMN id DROP DEFAULT;
```

### Testing Migration

All schema changes are covered by tests:

```bash
# Test RAG schema migration
uv run pytest tests/test_rag_store.py::test_metadata_tables_match_central_schema

# Test annotation sequence generation
uv run pytest tests/test_annotations_store.py

# Test ranking store optimizations
uv run pytest tests/test_ranking_store.py
```

### Questions?

See the commit message for PR merge commit or file an issue on GitHub.
