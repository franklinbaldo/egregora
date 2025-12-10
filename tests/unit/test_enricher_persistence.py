
from unittest.mock import MagicMock, call
from datetime import datetime, timezone
from egregora.agents.enricher import EnrichmentWorker, EnrichmentRuntimeContext
from egregora.data_primitives.document import Document, DocumentType

def test_persist_unified_versioning():
    # Mock connection
    mock_conn = MagicMock()
    # Setup return value for version query
    # First call: None (no existing version) -> should use version 1
    # Second call: 1 (existing version) -> should use version 2
    mock_conn.execute.return_value.fetchone.side_effect = [
        (None,), # For first document
        (1,),    # For second document
    ]

    mock_storage = MagicMock()
    mock_storage.ibis_conn.con = mock_conn

    # Mock context
    ctx = MagicMock(spec=EnrichmentRuntimeContext)
    ctx.storage = mock_storage
    ctx.library = None

    # Create worker
    worker = EnrichmentWorker(ctx)

    # Create document
    doc = Document(
        content="Test content",
        type=DocumentType.ENRICHMENT_URL,
        id="test-doc",
        metadata={"slug": "test", "title": "Test"}
    )

    # 1. Persist (Fresh)
    worker._persist_to_unified_tables(doc)

    # Verify first insert used version 1
    # We look for the call that inserted into entry_contents
    # We can inspect arguments
    calls = mock_conn.execute.call_args_list
    # The execute calls are: 1. SELECT MAX(version), 2. INSERT contents, 3. INSERT documents, 4. INSERT entry_contents
    # We expect 4 calls per persist
    assert len(calls) >= 4

    select_call = calls[0]
    assert "SELECT MAX(version_id)" in select_call[0][0]

    assoc_insert_call = calls[3]
    sql = assoc_insert_call[0][0]
    params = assoc_insert_call[0][1]
    assert "INSERT OR IGNORE INTO entry_contents" in sql
    # Params order: entry_id, content_id, version_id, created_at, order_index
    # version_id is index 2
    assert params[2] == 1

    # Reset mocks for second run
    mock_conn.reset_mock()
    mock_conn.execute.return_value.fetchone.side_effect = [(1,)]

    # 2. Persist (Update)
    worker._persist_to_unified_tables(doc)

    calls = mock_conn.execute.call_args_list
    assoc_insert_call = calls[3]
    params = assoc_insert_call[0][1]
    assert params[2] == 2 # Should be incremented

    print("Logic verification passed!")

if __name__ == "__main__":
    test_persist_unified_versioning()
