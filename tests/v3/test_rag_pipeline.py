import pytest
from pathlib import Path
from unittest.mock import MagicMock

from egregora_v3.core.context import build_context
from egregora_v3.features.rag.ingest import ingest_source
from egregora_v3.features.rag.build import build_embeddings
from egregora_v3.features.rag.query import query_rag
from egregora_v3.core.db import initialize_database, create_vss_index

# Mock embedding to be returned by the mocked client
MOCK_EMBEDDING = [0.1] * 768

@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Provides a temporary, isolated database path for testing."""
    return tmp_path / "test_egregora.db"

@pytest.fixture
def mock_gemini_client() -> MagicMock:
    """Mocks the GeminiEmbeddingClient to avoid actual API calls."""
    mock_client = MagicMock()
    mock_client.embed.return_value = [MOCK_EMBEDDING]
    return mock_client

@pytest.fixture
def test_context(temp_db_path: Path, mock_gemini_client: MagicMock):
    """
    Creates a test context with a temporary DB and a mocked Gemini client.
    """
    ctx = build_context(cli_overrides={"db_path": temp_db_path})
    ctx.embedding_client = mock_gemini_client

    initialize_database(ctx.conn, embedding_dim=ctx.settings.embedding_dim)
    create_vss_index(ctx.conn, metric=ctx.settings.vss_metric)

    yield ctx

    ctx.close()

@pytest.fixture
def test_source_file(tmp_path: Path) -> Path:
    """Creates a dummy source file for ingestion testing."""
    source_file = tmp_path / "test_doc.md"
    source_file.write_text("This is a test document about the Egregora project.")
    return source_file

def test_full_rag_pipeline(test_context, test_source_file: Path):
    """
    Tests the full RAG pipeline: ingest -> build -> query.
    """
    # 1. Ingest the source file
    ingest_source(test_context, test_source_file)

    chunk_count = test_context.conn.execute("SELECT count(*) FROM rag_chunks").fetchone()[0]
    assert chunk_count == 1

    # 2. Build the embeddings
    build_embeddings(test_context)

    test_context.embedding_client.embed.assert_called_once()

    vector_count = test_context.conn.execute("SELECT count(*) FROM rag_vectors").fetchone()[0]
    assert vector_count == 1

    # 3. Query the RAG pipeline
    query_text = "Tell me about Egregora"
    hits = query_rag(test_context, query_text)

    assert len(hits) == 1
    hit = hits[0]
    assert "This is a test document" in hit.chunk.text

    assert test_context.embedding_client.embed.call_count == 2
    test_context.embedding_client.embed.assert_called_with([query_text], task_type="retrieval_query")
