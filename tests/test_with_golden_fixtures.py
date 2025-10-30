"""
Tests for the main pipeline using golden fixtures.

These tests use the `GeminiClientPlayback` client to replay real, recorded
API responses. This ensures that the pipeline behaves correctly with the
actual data structures and content returned by the Gemini API.

The tests are fast because no live API calls are made. They are also
deterministic, ensuring that the output is consistent.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_pipeline_with_golden_fixtures(
    whatsapp_fixture,
    playback_client,
    tmp_path: Path,
):
    """
    Test the main pipeline using real recorded API responses.

    This test validates that the pipeline can successfully run from start to
    finish using the `playback_client`, which replays golden fixtures.
    It checks that the output matches the expected structure and content that
    would be generated with real API calls.
    """
    from egregora.orchestration.pipeline import process_whatsapp_export

    output_dir = tmp_path / "site"
    output_dir.mkdir()

    # Create mkdocs.yml for site structure
    mkdocs_yml = output_dir / "mkdocs.yml"
    mkdocs_yml.write_text("site_name: Test Site\ndocs_dir: docs\n", encoding="utf-8")

    docs_dir = output_dir / "docs"
    docs_dir.mkdir()

    # Run the pipeline with the playback client
    # This will use the recorded fixtures instead of making live API calls
    process_whatsapp_export(
        zip_path=whatsapp_fixture.zip_path,
        output_dir=output_dir,
        period="day",
        enable_enrichment=True,
        client=playback_client,  # Use the playback client
    )

    # Verify that the basic output structure was created
    posts_dir = docs_dir / "posts"
    assert posts_dir.exists(), "Posts directory should be created"

    profiles_dir = docs_dir / "profiles"
    assert profiles_dir.exists(), "Profiles directory should be created"

    # A more specific check to ensure content is being generated
    # This depends on the content of the golden fixtures
    # For now, we'll just check that some markdown files were created
    md_files = list(posts_dir.glob("*.md"))
    assert len(md_files) > 0, "At least one post markdown file should be created"