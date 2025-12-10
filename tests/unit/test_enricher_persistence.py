
from unittest.mock import MagicMock, ANY
from datetime import datetime, timezone
from egregora.agents.enricher import EnrichmentWorker, EnrichmentRuntimeContext
from egregora.data_primitives.document import Document, DocumentType

def test_persist_unified_versioning():
    # Mock storage backend
    mock_backend = MagicMock()

    mock_storage = MagicMock()
    mock_storage.ibis_conn = mock_backend

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
        metadata={"slug": "test", "title": "Test Title"}
    )

    # Persist
    worker._persist_to_unified_tables(doc)

    # Verify Ibis insert call
    mock_backend.insert.assert_called_once()
    call_args = mock_backend.insert.call_args
    table_name = call_args[0][0]
    data = call_args[0][1]

    assert table_name == "entry_versions"
    assert len(data) == 1
    row = data[0]

    # Verify fields
    assert row["atom_id"] == "test-doc"
    assert row["title"] == "Test Title"
    assert row["event_type"] == "enrichment"

    # Verify version_id is a large int (randomly generated)
    version_id = row["version_id"]
    assert isinstance(version_id, int)
    assert version_id > 0
    # It shouldn't be 1 (unless 1 in 2^63 chance)
    # The logic is uuid.uuid4().int & (1<<63)-1
    print(f"Generated version_id: {version_id}")

    print("Logic verification passed!")

if __name__ == "__main__":
    test_persist_unified_versioning()
