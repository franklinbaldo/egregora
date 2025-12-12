"""Tests for datetime-safe JSON serialization in LanceDB backend."""

from datetime import date, datetime, timezone

import pytest

from egregora.rag.lancedb_backend import _json_serialize_metadata


class TestJsonSerializeMetadata:
    """Test _json_serialize_metadata handles datetime objects."""

    def test_serializes_datetime_to_iso(self) -> None:
        """Datetime objects should be serialized to ISO format strings."""
        dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        metadata = {"created_at": dt, "title": "Test"}
        
        result = _json_serialize_metadata(metadata)
        
        assert '"created_at": "2024-03-15T10:30:00+00:00"' in result
        assert '"title": "Test"' in result

    def test_serializes_date_to_iso(self) -> None:
        """Date objects should be serialized to ISO format strings."""
        d = date(2024, 3, 15)
        metadata = {"published_date": d}
        
        result = _json_serialize_metadata(metadata)
        
        assert '"published_date": "2024-03-15"' in result

    def test_handles_mixed_types(self) -> None:
        """Should handle metadata with various types including datetime."""
        dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        metadata = {
            "title": "Test Post",
            "created_at": dt,
            "count": 42,
            "active": True,
            "tags": ["a", "b"],
        }
        
        result = _json_serialize_metadata(metadata)
        
        # Should not raise and should contain all fields
        assert "Test Post" in result
        assert "2024-03-15" in result
        assert "42" in result
        assert "true" in result.lower()
        assert '["a", "b"]' in result or '["a","b"]' in result

    def test_raises_on_unsupported_type(self) -> None:
        """Should raise TypeError for unsupported types."""
        
        class CustomClass:
            pass
        
        metadata = {"custom": CustomClass()}
        
        with pytest.raises(TypeError, match="not JSON serializable"):
            _json_serialize_metadata(metadata)

    def test_empty_metadata(self) -> None:
        """Empty metadata should return empty JSON object."""
        result = _json_serialize_metadata({})
        assert result == "{}"
