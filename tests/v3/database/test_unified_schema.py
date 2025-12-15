import ibis
import ibis.expr.datatypes as dt
import pytest
from egregora.database import ir_schema

def test_unified_schema_structure():
    """Verify that UNIFIED_SCHEMA is defined correctly in ir_schema."""

    # Check if UNIFIED_SCHEMA is exported
    assert hasattr(ir_schema, "UNIFIED_SCHEMA"), "UNIFIED_SCHEMA is not defined in ir_schema"

    schema = ir_schema.UNIFIED_SCHEMA

    # Verify it is an Ibis schema
    assert isinstance(schema, ibis.Schema)

    # Verify Core Atom Fields
    assert "id" in schema
    assert schema["id"].is_string()

    assert "title" in schema
    assert schema["title"].is_string()

    assert "updated" in schema
    assert schema["updated"].is_timestamp()

    assert "published" in schema
    assert schema["published"].is_timestamp()

    assert "summary" in schema
    assert schema["summary"].is_string()

    assert "content" in schema
    assert schema["content"].is_string()

    assert "content_type" in schema
    assert schema["content_type"].is_string()

    assert "source" in schema
    assert schema["source"].is_json()

    # Verify List/Complex Fields (JSON)
    assert "links" in schema
    assert schema["links"].is_json()

    assert "authors" in schema
    assert schema["authors"].is_json()

    assert "contributors" in schema
    assert schema["contributors"].is_json()

    assert "categories" in schema
    assert schema["categories"].is_json()

    assert "in_reply_to" in schema
    assert schema["in_reply_to"].is_json()

    # Verify V3 Extensions
    assert "extensions" in schema
    assert schema["extensions"].is_json()

    assert "internal_metadata" in schema
    assert schema["internal_metadata"].is_json()

    assert "doc_type" in schema
    assert schema["doc_type"].is_string()

    assert "status" in schema
    assert schema["status"].is_string()

def test_unified_schema_nullability():
    """Verify nullability of optional fields."""
    schema = ir_schema.UNIFIED_SCHEMA

    # Optional fields should be nullable
    assert schema["published"].nullable
    assert schema["summary"].nullable
    assert schema["content"].nullable
    assert schema["content_type"].nullable
    assert schema["source"].nullable
    assert schema["in_reply_to"].nullable

    # Required fields should NOT be nullable
    # Note: Ibis behavior on nullability check might vary, but usually dt.string means NOT NULL
    # and dt.String(nullable=True) means NULL.
    # Let's check strictness if possible, otherwise rely on previous test types.
    assert not schema["id"].nullable
    assert not schema["title"].nullable
    assert not schema["updated"].nullable
