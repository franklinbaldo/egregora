import httpx
import pytest
import respx

from egregora.rag.embeddings import (
    _get_timeout,
    embed_text,
    embed_texts_in_batch,
    is_rag_available,
)
from egregora.rag.exceptions import EmbeddingAPIError

# Constants for mocking
FAKE_API_KEY = "test-key"
EMBEDDING_MODEL = "models/text-embedding-004"
GENAI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    """Mock time.sleep to avoid waiting in retry loops during tests."""
    monkeypatch.setattr("time.sleep", lambda x: None)


@pytest.fixture
def mock_google_api_key(monkeypatch):
    """Fixture to mock the Google API key."""
    monkeypatch.setenv("GOOGLE_API_KEY", FAKE_API_KEY)
    return FAKE_API_KEY


@pytest.mark.usefixtures("mock_google_api_key")
def test_is_rag_available():
    """Test that RAG is available when the API key is set."""
    assert is_rag_available()


def test_is_rag_not_available(monkeypatch):
    """Test that RAG is not available when the API key is not set."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert not is_rag_available()


@respx.mock
@pytest.mark.usefixtures("mock_google_api_key")
def test_embed_text_success():
    """Test successful embedding of a single text."""
    mock_route = respx.post(f"{GENAI_API_BASE}/{EMBEDDING_MODEL}:embedContent").mock(
        return_value=httpx.Response(
            200,
            json={"embedding": {"values": [0.1] * 768}},
        )
    )

    embedding = embed_text("Hello world", model=EMBEDDING_MODEL)
    assert len(embedding) == 768
    assert mock_route.called


@respx.mock
@pytest.mark.usefixtures("mock_google_api_key")
def test_embed_text_rate_limit_and_retry():
    """Test that rate limits are handled with retries."""
    mock_route = respx.post(f"{GENAI_API_BASE}/{EMBEDDING_MODEL}:embedContent").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "1"}),
            httpx.Response(200, json={"embedding": {"values": [0.2] * 768}}),
        ]
    )

    embedding = embed_text("Test retry", model=EMBEDDING_MODEL)
    assert len(embedding) == 768
    assert mock_route.call_count == 2


@respx.mock
@pytest.mark.usefixtures("mock_google_api_key")
def test_embed_text_api_error():
    """Test that a non-retriable API error raises an exception."""
    respx.post(f"{GENAI_API_BASE}/{EMBEDDING_MODEL}:embedContent").mock(return_value=httpx.Response(500))

    # The tenacity decorator with reraise=True will raise the last exception
    # which is EmbeddingAPIError in this case.
    with pytest.raises(EmbeddingAPIError) as exc_info:
        embed_text("This will fail", model=EMBEDDING_MODEL)

    assert exc_info.value.status_code == 500


@respx.mock
@pytest.mark.usefixtures("mock_google_api_key")
def test_embed_texts_in_batch_single_chunk():
    """Test batch embedding for a single chunk (<= 100 texts)."""
    mock_route = respx.post(f"{GENAI_API_BASE}/{EMBEDDING_MODEL}:batchEmbedContents").mock(
        return_value=httpx.Response(
            200,
            json={
                "embeddings": [
                    {"values": [0.3] * 768},
                    {"values": [0.4] * 768},
                ]
            },
        )
    )

    embeddings = embed_texts_in_batch(["Text 1", "Text 2"], model=EMBEDDING_MODEL)
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 768
    assert mock_route.called


@respx.mock
@pytest.mark.usefixtures("mock_google_api_key")
def test_embed_texts_in_batch_multiple_chunks():
    """Test batch embedding that requires multiple API calls."""
    texts = [f"Text {i}" for i in range(150)]
    mock_route = respx.post(f"{GENAI_API_BASE}/{EMBEDDING_MODEL}:batchEmbedContents").mock(
        side_effect=[
            httpx.Response(
                200,
                json={"embeddings": [{"values": [0.5] * 768} for _ in range(100)]},
            ),
            httpx.Response(
                200,
                json={"embeddings": [{"values": [0.6] * 768} for _ in range(50)]},
            ),
        ]
    )

    embeddings = embed_texts_in_batch(texts, model=EMBEDDING_MODEL)
    assert len(embeddings) == 150
    assert mock_route.call_count == 2
    assert embeddings[0][0] == 0.5
    assert embeddings[100][0] == 0.6


def test_get_timeout():
    """Test that the default timeout is returned."""
    assert _get_timeout() == 60.0
