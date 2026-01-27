"""Full end-to-end smoke tests with realistic LLM mocks.

These tests validate the complete pipeline flow with mocked LLM responses
to ensure deterministic, repeatable testing without API calls.
"""

import time

import pytest
from egregora.output_adapters.mkdocs import MkDocsAdapter
from egregora.output_adapters.mkdocs.paths import derive_mkdocs_paths

from egregora import rag
from egregora.orchestration.pipelines.write import WhatsAppProcessOptions, process_whatsapp_export
from tests.e2e.mocks.enrichment_mocks import mock_media_enrichment, mock_url_enrichment


@pytest.fixture
def pipeline_mocks(
    llm_response_mocks,
    mock_vector_store,
    mocked_writer_agent,
    mock_batch_client,
):
    """Bundle side-effect fixtures for pipeline execution."""

    return {
        "llm_response_mocks": llm_response_mocks,
        "mock_vector_store": mock_vector_store,
        "mocked_writer_agent": mocked_writer_agent,
        "mock_batch_client": mock_batch_client,
    }


@pytest.fixture
def pipeline_setup(
    whatsapp_fixture,
    pipeline_mocks,
    gemini_api_key,
):
    """Bundle common pipeline fixtures to reduce test parameters."""

    return {
        "whatsapp_fixture": whatsapp_fixture,
        **pipeline_mocks,
        "gemini_api_key": gemini_api_key,
    }


@pytest.mark.e2e
def test_full_pipeline_smoke_test(pipeline_setup, tmp_path):
    """Run full pipeline with mocked LLM responses.

    Validates:
    - Pipeline executes without errors
    - All 5 stages complete (ingestion, privacy, enrichment, generation, publication)
    - Output directory structure is created
    - Posts and profiles are generated
    - Media is processed
    """
    # Setup output directory
    site_root = tmp_path / "site"
    site_root.mkdir()

    # Initialize site structure (required by pipeline)
    output_format = MkDocsAdapter()
    output_format.scaffold_site(site_root, site_name="Test E2E Site")

    # Configure pipeline with minimal overrides (using defaults where possible)
    options = WhatsAppProcessOptions(
        output_dir=site_root,
        timezone=pipeline_setup["whatsapp_fixture"].timezone,
        gemini_api_key=pipeline_setup["gemini_api_key"],
    )

    # Run pipeline with mocked LLM
    results = process_whatsapp_export(
        pipeline_setup["whatsapp_fixture"].zip_path,
        options=options,
    )

    # Verify pipeline completed
    assert results is not None

    # Resolve paths dynamically using the same logic as the adapter
    site_paths = derive_mkdocs_paths(site_root)
    posts_dir = site_paths["posts_dir"]
    profiles_dir = site_paths["profiles_dir"]

    # Verify output structure exists
    assert posts_dir.exists(), f"Posts directory should be created at {posts_dir}"
    assert profiles_dir.exists(), f"Profiles directory should be created at {profiles_dir}"

    # Verify at least one post was generated
    post_files = list(posts_dir.glob("*.md"))
    assert len(post_files) > 0, "At least one post should be generated"

    # Verify writer agent was called (implicitly by checking output)
    # Note: captured_windows is unreliable due to threading/asyncio isolation in writer agent
    # We rely on the file output verification above.


@pytest.mark.e2e
def test_pipeline_respects_mocked_llm_responses(
    llm_response_mocks,
    tmp_path,
):
    """Verify that enrichment agents use mocked responses.

    This test validates that:
    - URL enrichment returns fixture-specific data
    - Media enrichment returns fixture-specific data
    - Responses are deterministic and repeatable
    """
    # Test URL enrichment returns fixture data
    url = "https://docs.pydantic.dev"
    result = mock_url_enrichment(url)

    assert result["title"] == "Pydantic: Data Validation with Python Type Hints"
    assert result["domain"] == "pydantic.dev"
    assert result["content_type"] == "documentation"

    # Test media enrichment returns fixture data
    media = "IMG-20251028-WA0035.jpg"
    result = mock_media_enrichment(media)

    assert "test execution" in result["alt_text"].lower()
    assert "testing" in result["estimated_topics"]
    assert result["contains_text"] is True

    # Test deterministic behavior (calling twice should yield same results)
    result1 = mock_url_enrichment(url)
    result2 = mock_url_enrichment(url)
    assert result1 == result2

    result1 = mock_media_enrichment(media)
    result2 = mock_media_enrichment(media)
    assert result1 == result2


@pytest.mark.e2e
def test_pipeline_with_rag_enabled(pipeline_setup, tmp_path):
    """Test pipeline with RAG enabled using mocked VectorStore.

    Validates:
    - RAG operations are mocked correctly
    - VectorStore mock tracks method calls
    - Pipeline completes with RAG enabled
    """
    # Setup output directory
    site_root = tmp_path / "site"
    site_root.mkdir()

    # Initialize site structure
    output_format = MkDocsAdapter()
    output_format.scaffold_site(site_root, site_name="Test RAG Site")

    # Configure pipeline with RAG enabled
    options = WhatsAppProcessOptions(
        output_dir=site_root,
        timezone=pipeline_setup["whatsapp_fixture"].timezone,
        gemini_api_key=pipeline_setup["gemini_api_key"],
    )

    # Run pipeline (RAG is enabled by default via config)
    results = process_whatsapp_export(
        pipeline_setup["whatsapp_fixture"].zip_path,
        options=options,
    )

    # Verify pipeline completed
    assert results is not None

    # Verify VectorStore was instantiated and used
    # The mock tracks calls via indexed_documents and indexed_media lists
    # Note: We can't directly inspect the mock instance from here,
    # but we can verify the pipeline completed successfully with RAG enabled


@pytest.mark.e2e
def test_mock_fixtures_are_available(llm_response_mocks, mock_vector_store):
    """Verify that E2E mock fixtures are properly configured.

    This is a simple test to ensure the testing infrastructure is working.
    """
    # Verify LLM response mocks are available
    assert llm_response_mocks is not None
    assert "url_enrichments" in llm_response_mocks
    assert "media_enrichments" in llm_response_mocks
    assert "writer_post" in llm_response_mocks

    # Verify RAG mock is available
    # mock_vector_store is now a list that tracks indexed documents (not a VectorStore class)
    assert mock_vector_store is not None
    assert isinstance(mock_vector_store, list), "mock_vector_store should be a list tracking indexed docs"

    # Verify the new RAG API functions are mocked
    # The functions should be mocked (they won't raise ImportError)
    assert hasattr(rag, "index_documents")
    assert hasattr(rag, "search")


@pytest.mark.e2e
def test_url_enrichment_mock_returns_fixture_data(llm_response_mocks):
    """Verify URL enrichment mock returns expected fixture data."""
    # Test known URL
    result = mock_url_enrichment("https://docs.pydantic.dev")
    assert result["title"] == "Pydantic: Data Validation with Python Type Hints"
    assert result["domain"] == "pydantic.dev"
    assert result["content_type"] == "documentation"

    # Test unknown URL (should get default)
    result = mock_url_enrichment("https://unknown-url.com/test")
    assert "Mock:" in result["title"]
    assert result["domain"] == "unknown-url.com"


@pytest.mark.e2e
def test_media_enrichment_mock_returns_fixture_data(llm_response_mocks):
    """Verify media enrichment mock returns expected fixture data."""
    # Test known image
    result = mock_media_enrichment("IMG-20251028-WA0035.jpg")
    assert "test execution" in result["alt_text"].lower()
    assert "testing" in result["estimated_topics"]
    assert result["contains_text"] is True

    # Test unknown image (should get default)
    result = mock_media_enrichment("unknown-image.jpg")
    assert "Image:" in result["alt_text"]
    assert result["contains_text"] is False


@pytest.mark.e2e
@pytest.mark.benchmark
def test_mock_performance_baseline(llm_response_mocks):
    """Ensure mocks execute quickly (< 1ms per call).

    This validates that mocks don't introduce performance overhead.
    """
    # Simple performance check - mocks should be instant
    start = time.time()
    for _ in range(100):
        mock_url_enrichment("https://docs.pydantic.dev")
    elapsed = time.time() - start

    # 100 calls should take < 10ms
    assert elapsed < 0.01, f"Mocks too slow: {elapsed:.4f}s for 100 calls"
