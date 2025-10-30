import unittest.mock as mock

from egregora.utils.batch import EmbeddingBatchRequest
from egregora.utils.smart_client import SmartGeminiClient


def test_smart_client_uses_individual_for_small_batches():
    """Verify that requests below the threshold use individual calls."""
    mock_client = mock.MagicMock()
    smart_client = SmartGeminiClient(mock_client, "gemini-pro", batch_threshold=10)

    # Patch the internal methods to monitor calls
    smart_client._embed_individual = mock.MagicMock()
    smart_client._embed_batch = mock.MagicMock()

    requests = [EmbeddingBatchRequest(text=f"req_{i}") for i in range(9)]
    smart_client.embed_content(requests)

    smart_client._embed_individual.assert_called_once_with(requests)
    smart_client._embed_batch.assert_not_called()


def test_smart_client_uses_batch_for_large_batches():
    """Verify that requests at or above the threshold use batch calls."""
    mock_client = mock.MagicMock()
    smart_client = SmartGeminiClient(mock_client, "gemini-pro", batch_threshold=10)

    smart_client._embed_individual = mock.MagicMock()
    smart_client._embed_batch = mock.MagicMock()

    requests = [EmbeddingBatchRequest(text=f"req_{i}") for i in range(10)]
    smart_client.embed_content(requests)

    smart_client._embed_individual.assert_not_called()
    smart_client._embed_batch.assert_called_once_with(requests)


def test_force_batch_overrides_threshold():
    """Verify that force_batch=True uses the batch method even for small N."""
    mock_client = mock.MagicMock()
    smart_client = SmartGeminiClient(mock_client, "gemini-pro", batch_threshold=10)

    smart_client._embed_individual = mock.MagicMock()
    smart_client._embed_batch = mock.MagicMock()

    requests = [EmbeddingBatchRequest(text=f"req_{i}") for i in range(5)]
    smart_client.embed_content(requests, force_batch=True)

    smart_client._embed_individual.assert_not_called()
    smart_client._embed_batch.assert_called_once_with(requests)


def test_force_individual_overrides_threshold():
    """Verify that force_individual=True uses the individual method even for large N."""
    mock_client = mock.MagicMock()
    smart_client = SmartGeminiClient(mock_client, "gemini-pro", batch_threshold=10)

    smart_client._embed_individual = mock.MagicMock()
    smart_client._embed_batch = mock.MagicMock()

    requests = [EmbeddingBatchRequest(text=f"req_{i}") for i in range(20)]
    smart_client.embed_content(requests, force_individual=True)

    smart_client._embed_individual.assert_called_once_with(requests)
    smart_client._embed_batch.assert_not_called()