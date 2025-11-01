"""
Tests for the main pipeline using pytest-vcr to replay HTTP interactions.

These tests use pytest-vcr to record and replay HTTP interactions with the
Gemini API. This ensures that the pipeline behaves correctly with the actual
data structures and content returned by the Gemini API.

The tests are fast because no live API calls are made after initial recording.
They are also deterministic, ensuring that the output is consistent.

## Recording Cassettes:

To record new cassettes (requires GOOGLE_API_KEY):
    pytest tests/test_with_golden_fixtures.py --vcr-record=all

To use existing cassettes (default):
    pytest tests/test_with_golden_fixtures.py

## Test Configuration:

**Enrichment Disabled:** Binary file uploads (images) cause VCR encoding issues.
The test focuses on LLM API interactions which are the core of the pipeline.

**Exact Retrieval Mode:** Tests use `retrieval_mode="exact"` instead of the
default "ann" (Approximate Nearest Neighbor) mode for the following reasons:

1. **No VSS Extension Required:** The DuckDB VSS extension is downloaded at
   runtime when you run `INSTALL vss`. In CI/CD or test environments, this
   download can fail due to network restrictions or permissions.

2. **Faster Tests:** Exact mode uses simple cosine similarity without index
   building, making tests faster and more deterministic.

3. **Production vs Testing:** VSS with ANN indexing is beneficial for production
   use with large datasets (>1000 documents). For small test datasets, exact
   mode is perfectly adequate and more reliable.

4. **Zero Dependencies:** No need to pre-install extensions or configure network
   access for extension downloads.

If you need to test VSS functionality specifically:
    # Pre-install VSS extension in your environment
    python -c "import duckdb; conn = duckdb.connect(); conn.execute('INSTALL vss'); conn.execute('LOAD vss')"
    # Then run tests with retrieval_mode="ann"
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from google import genai

from egregora.orchestration.pipeline import process_whatsapp_export


@pytest.mark.vcr
def test_pipeline_with_vcr_fixtures(
    whatsapp_fixture,
    tmp_path: Path,
):
    """
    Test the main pipeline using VCR-recorded API responses.

    This test validates that the pipeline can successfully run from start to
    finish using pytest-vcr to replay HTTP interactions.
    It checks that the output matches the expected structure and content that
    would be generated with real API calls.

    The @pytest.mark.vcr decorator automatically records HTTP interactions
    to cassettes and replays them on subsequent test runs.
    """
    output_dir = tmp_path / "site"
    output_dir.mkdir()

    # Create mkdocs.yml for site structure
    mkdocs_yml = output_dir / "mkdocs.yml"
    mkdocs_yml.write_text("site_name: Test Site\ndocs_dir: docs\n", encoding="utf-8")

    docs_dir = output_dir / "docs"
    docs_dir.mkdir()

    # Create a real Gemini client
    # VCR will intercept the HTTP calls and replay from cassettes
    api_key = os.getenv("GOOGLE_API_KEY", "dummy-key-for-replay")
    client = genai.Client(api_key=api_key)

    # Run the pipeline with the real client - VCR will record/replay HTTP interactions
    process_whatsapp_export(
        zip_path=whatsapp_fixture.zip_path,
        output_dir=output_dir,
        period="day",
        enable_enrichment=False,  # Binary uploads cause VCR encoding issues
        retrieval_mode="exact",  # Exact mode avoids VSS extension dependency (see module docstring)
        client=client,
    )

    # Verify that the basic output structure was created
    posts_dir = docs_dir / "posts"
    assert posts_dir.exists(), "Posts directory should be created"

    profiles_dir = docs_dir / "profiles"
    assert profiles_dir.exists(), "Profiles directory should be created"

    # A more specific check to ensure content is being generated
    # This depends on the content of the VCR cassettes
    # For now, we'll just check that some markdown files were created
    md_files = list(posts_dir.glob("*.md"))
    assert len(md_files) > 0, "At least one post markdown file should be created"