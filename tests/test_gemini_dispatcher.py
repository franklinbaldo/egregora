from unittest import mock

from egregora.utils.batch import EmbeddingBatchRequest
from egregora.utils.gemini_dispatcher import GeminiDispatcher, SmartGeminiClient


def test_gemini_dispatcher_uses_individual_for_small_batches():
    """Verify that requests below the threshold use individual calls."""
    mock_client = mock.MagicMock()
    dispatcher = GeminiDispatcher(mock_client, "gemini-pro", batch_threshold=10)

    # Patch the internal dispatchers to monitor calls
    dispatcher._embedding_dispatcher._execute_individual = mock.MagicMock(return_value=[])
    dispatcher._embedding_dispatcher._execute_batch = mock.MagicMock()

    requests = [EmbeddingBatchRequest(text=f"req_{i}") for i in range(9)]
    dispatcher.embed_content(requests)

    dispatcher._embedding_dispatcher._execute_individual.assert_called_once_with(requests)
    dispatcher._embedding_dispatcher._execute_batch.assert_not_called()


def test_gemini_dispatcher_uses_batch_for_large_batches():
    """Verify that requests at or above the threshold use batch calls."""
    mock_client = mock.MagicMock()
    dispatcher = GeminiDispatcher(mock_client, "gemini-pro", batch_threshold=10)

    dispatcher._embedding_dispatcher._execute_individual = mock.MagicMock()
    dispatcher._embedding_dispatcher._execute_batch = mock.MagicMock(return_value=[])

    requests = [EmbeddingBatchRequest(text=f"req_{i}") for i in range(10)]
    dispatcher.embed_content(requests)

    dispatcher._embedding_dispatcher._execute_individual.assert_not_called()
    # Check that batch was called with the requests (kwargs are variable)
    assert dispatcher._embedding_dispatcher._execute_batch.called
    call_args = dispatcher._embedding_dispatcher._execute_batch.call_args
    assert call_args[0][0] == requests  # First positional arg should be requests


def test_force_batch_overrides_threshold():
    """Verify that force_batch=True uses the batch method even for small N."""
    mock_client = mock.MagicMock()
    dispatcher = GeminiDispatcher(mock_client, "gemini-pro", batch_threshold=10)

    dispatcher._embedding_dispatcher._execute_individual = mock.MagicMock()
    dispatcher._embedding_dispatcher._execute_batch = mock.MagicMock(return_value=[])

    requests = [EmbeddingBatchRequest(text=f"req_{i}") for i in range(5)]
    dispatcher.embed_content(requests, force_batch=True)

    dispatcher._embedding_dispatcher._execute_individual.assert_not_called()
    # Check that batch was called
    assert dispatcher._embedding_dispatcher._execute_batch.called
    call_args = dispatcher._embedding_dispatcher._execute_batch.call_args
    assert call_args[0][0] == requests


def test_force_individual_overrides_threshold():
    """Verify that force_individual=True uses the individual method even for large N."""
    mock_client = mock.MagicMock()
    dispatcher = GeminiDispatcher(mock_client, "gemini-pro", batch_threshold=10)

    dispatcher._embedding_dispatcher._execute_individual = mock.MagicMock(return_value=[])
    dispatcher._embedding_dispatcher._execute_batch = mock.MagicMock()

    requests = [EmbeddingBatchRequest(text=f"req_{i}") for i in range(20)]
    dispatcher.embed_content(requests, force_individual=True)

    dispatcher._embedding_dispatcher._execute_individual.assert_called_once_with(requests)
    dispatcher._embedding_dispatcher._execute_batch.assert_not_called()


def test_backward_compatibility_with_smart_client_alias():
    """Verify that SmartGeminiClient alias still works."""
    mock_client = mock.MagicMock()
    # Should work the same as GeminiDispatcher
    client = SmartGeminiClient(mock_client, "gemini-pro")
    assert isinstance(client, GeminiDispatcher)
