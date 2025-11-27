import ibis
import ibis.expr.datatypes as dt

# The schema for a single document stored in Parquet
DOCUMENT_PARQUET_SCHEMA = ibis.schema(
    {
        "id": dt.string,  # UUIDv5
        "slug": dt.string,
        "type": dt.string,  # 'post', 'profile', 'journal'
        "title": dt.string,
        "content": dt.string,  # The raw markdown
        "summary": dt.string,
        "published_date": dt.date,
        # Complex types stored as Arrays/Structs (Native Parquet support!)
        "authors": dt.Array(dt.string),
        "tags": dt.Array(dt.string),
        # Catch-all for extra fields (JSON string for flexibility)
        "metadata_json": dt.string,
        "created_at": dt.timestamp,
        "updated_at": dt.timestamp,
    }
)
