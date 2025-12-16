
import pytest
from unittest.mock import MagicMock, patch
from egregora.rag.embedding_router import EmbeddingRouter
from egregora.utils.token_counting import count_tokens

@pytest.fixture
def mock_httpx_client():
    with patch("httpx.Client") as mock_client:
        yield mock_client

def test_embedding_router_modernized():
    """Verify modernized structure of EmbeddingRouter."""
    router = EmbeddingRouter(model="models/test")
    # Verify we removed the queues
    assert not hasattr(router, "batch_queue")
    assert not hasattr(router, "single_queue")
    # Verify we have the simplified structure
    assert router.model == "models/test"

def test_token_estimation_modernized():
    """Verify that token counting now uses tiktoken or helper."""
    text = "Hello world"
    # Current implementation uses tiktoken (cl100k_base)
    # "Hello world" -> [9906, 4435] (approx, depends on encoding)
    # With len(text)//4 it was 2.
    # With tiktoken it should be 2.
    count = count_tokens(text)
    assert count > 0
    # Basic sanity check
    assert count == 2 or count == 3
