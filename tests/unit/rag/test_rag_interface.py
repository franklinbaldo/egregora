import pytest

from egregora.rag import get_backend
from egregora.rag.backend import VectorStore
from egregora.rag.lancedb_backend import LanceDBRAGBackend


def test_lancedb_backend_implements_vector_store():
    """
    RED TEST: Verify LanceDBRAGBackend implements VectorStore protocol.
    Currently fails because it doesn't inherit and missing methods.
    """
    assert issubclass(LanceDBRAGBackend, VectorStore)

    # Check for required methods
    assert hasattr(LanceDBRAGBackend, "add")
    assert hasattr(LanceDBRAGBackend, "query")
    assert hasattr(LanceDBRAGBackend, "delete")
    assert hasattr(LanceDBRAGBackend, "count")


def test_rag_module_uses_vector_store_interface():
    """
    RED TEST: Verify high-level RAG functions work with the backend.
    Currently fails because of method mismatch (add vs index_documents) and import errors.
    """
    try:
        backend = get_backend()
    except (ImportError, NameError):
        pytest.fail("Failed to import/init backend")

    # If backend is a Mock (in tests), isinstance might fail if spec is not set.
    # We check for structural compliance (duck typing) instead.
    assert hasattr(backend, "add")
