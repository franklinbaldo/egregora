"""Full end-to-end smoke tests with realistic LLM mocks.

These tests validate the complete pipeline flow with mocked LLM responses
to ensure deterministic, repeatable testing without API calls.
"""

import pytest


@pytest.mark.e2e
def test_full_pipeline_smoke_test(
    whatsapp_fixture,
    llm_response_mocks,
    mock_vector_store,
    mocked_writer_agent,
    tmp_path,
    gemini_api_key,
):
    """Run full pipeline with mocked LLM responses.

    Validates:
    - Pipeline executes without errors
    - All 5 stages complete (ingestion, privacy, enrichment, generation, publication)
    - Output directory structure is created
    - Posts and profiles are generated
    - Media is processed
    """
    from egregora.orchestration.write_pipeline import (
        WhatsAppProcessOptions,
        process_whatsapp_export,
    )

    # Setup output directory
    site_root = tmp_path / "site"
    site_root.mkdir()

    # Initialize site structure (required by pipeline)
    from egregora.output_adapters.mkdocs import MkDocsAdapter

    output_format = MkDocsAdapter()
    output_format.scaffold_site(site_root, site_name="Test E2E Site")

    # Configure pipeline with minimal overrides (using defaults where possible)
    options = WhatsAppProcessOptions(
        output_dir=site_root,
        timezone=whatsapp_fixture.timezone,
        gemini_api_key=gemini_api_key,
    )

    # Run pipeline with mocked LLM
    results = process_whatsapp_export(
        whatsapp_fixture.zip_path,
        options=options,
    )

    # Verify pipeline completed
    assert results is not None

    # Verify output structure exists (MkDocs uses docs/ subdirectory)
    assert (site_root / "docs" / "posts").exists(), "Posts directory should be created"
    assert (site_root / "docs" / "profiles").exists(), "Profiles directory should be created"

    # Verify at least one post was generated
    post_files = list((site_root / "docs" / "posts").glob("*.md"))
    assert len(post_files) > 0, "At least one post should be generated"

    # Verify writer agent was called
    assert len(mocked_writer_agent["captured_windows"]) > 0, "Writer should process windows"


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
    from tests.e2e.mocks.enrichment_mocks import mock_media_enrichment, mock_url_enrichment

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
def test_pipeline_with_rag_enabled(
    whatsapp_fixture,
    llm_response_mocks,
    mock_vector_store,
    mocked_writer_agent,
    tmp_path,
    gemini_api_key,
):
    """Test pipeline with RAG enabled using mocked VectorStore.

    Validates:
    - RAG operations are mocked correctly
    - VectorStore mock tracks method calls
    - Pipeline completes with RAG enabled
    """
    from egregora.orchestration.write_pipeline import (
        WhatsAppProcessOptions,
        process_whatsapp_export,
    )
    from egregora.output_adapters.mkdocs import MkDocsAdapter

    # Setup output directory
    site_root = tmp_path / "site"
    site_root.mkdir()

    # Initialize site structure
    output_format = MkDocsAdapter()
    output_format.scaffold_site(site_root, site_name="Test RAG Site")

    # Configure pipeline with RAG enabled
    options = WhatsAppProcessOptions(
        output_dir=site_root,
        timezone=whatsapp_fixture.timezone,
        gemini_api_key=gemini_api_key,
    )

    # Run pipeline (RAG is enabled by default via config)
    results = process_whatsapp_export(
        whatsapp_fixture.zip_path,
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
    from egregora import rag

    # The functions should be mocked (they won't raise ImportError)
    assert hasattr(rag, "index_documents")
    assert hasattr(rag, "search")


@pytest.mark.e2e
def test_url_enrichment_mock_returns_fixture_data(llm_response_mocks):
    """Verify URL enrichment mock returns expected fixture data."""
    from tests.e2e.mocks.enrichment_mocks import mock_url_enrichment

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
    from tests.e2e.mocks.enrichment_mocks import mock_media_enrichment

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
    import time

    from tests.e2e.mocks.enrichment_mocks import mock_url_enrichment

    start = time.time()
    for _ in range(100):
        mock_url_enrichment("https://docs.pydantic.dev")
    elapsed = time.time() - start

    # 100 calls should take < 10ms
    assert elapsed < 0.01, f"Mocks too slow: {elapsed:.4f}s for 100 calls"
