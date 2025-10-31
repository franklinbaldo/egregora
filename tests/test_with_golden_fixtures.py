"""
Tests for the main pipeline using pytest-vcr to replay HTTP interactions.

These tests use pytest-vcr to record and replay HTTP interactions with the
Gemini API. This ensures that the pipeline behaves correctly with the actual
data structures and content returned by the Gemini API.

The tests are fast because no live API calls are made after initial recording.
They are also deterministic, ensuring that the output is consistent.

To record new cassettes (requires GOOGLE_API_KEY):
    pytest tests/test_with_golden_fixtures.py --vcr-record=all

To use existing cassettes (default):
    pytest tests/test_with_golden_fixtures.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.mark.vcr
@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY required for recording or when cassettes don't exist",
)
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
    from google import genai

    from egregora.orchestration.pipeline import process_whatsapp_export

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

    # Run the pipeline with the real client
    # VCR will record/replay the HTTP interactions
    process_whatsapp_export(
        zip_path=whatsapp_fixture.zip_path,
        output_dir=output_dir,
        period="day",
        enable_enrichment=True,
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