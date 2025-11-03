"""
End-to-end pipeline tests using deterministic mock Gemini responses.

The `mock_batch_client` fixture swaps out all Gemini HTTP interactions with
predictable in-memory stubs. This lets the pipeline run without an API key
while still exercising the orchestration, RAG, and post-writing logic.

The test keeps enrichment disabled (binary uploads are tricky to stub) and
forces `retrieval_mode="exact"` to avoid optional extensions. To exercise
VSS-specific code paths, run the pipeline manually with the DuckDB VSS
extension pre-installed.
"""

from __future__ import annotations

import os
from pathlib import Path

from tests.mock_batch_client import create_mock_genai_client

from egregora.orchestration.pipeline import process_whatsapp_export


def test_pipeline_with_golden_fixtures(
    whatsapp_fixture,
    tmp_path: Path,
    mock_batch_client,
):
    """Run the full pipeline using deterministic Gemini mock responses."""
    output_dir = tmp_path / "site"
    output_dir.mkdir()

    # Create mkdocs.yml for site structure
    mkdocs_yml = output_dir / "mkdocs.yml"
    mkdocs_yml.write_text("site_name: Test Site\ndocs_dir: docs\n", encoding="utf-8")

    docs_dir = output_dir / "docs"
    docs_dir.mkdir()

    # Create VCR-compatible client that uses raw HTTP calls
    # This works with VCR because it bypasses the genai SDK's complex response parsing
    api_key = os.getenv("GOOGLE_API_KEY", "dummy-key-for-replay")
    client = create_mock_genai_client(api_key=api_key)

    # Run the pipeline with the real client - VCR will record/replay HTTP interactions
    # NOTE: Enrichment disabled because VCR cannot serialize binary file uploads (images)
    # Media enrichment is tested separately in test_fast_with_mock.py
    process_whatsapp_export(
        zip_path=whatsapp_fixture.zip_path,
        output_dir=output_dir,
        period="day",
        enable_enrichment=False,  # VCR limitation: binary uploads cause serialization errors
        retrieval_mode="exact",  # Exact mode avoids VSS extension dependency (see module docstring)
        client=client,
    )

    # Verify that the basic output structure was created
    posts_dir = docs_dir / "posts"
    assert posts_dir.exists(), "Posts directory should be created"

    profiles_dir = docs_dir / "profiles"
    assert profiles_dir.exists(), "Profiles directory should be created"

    # Verify the site contains markdown artifacts (scaffolding + generated files)
    markdown_files = list(docs_dir.rglob("*.md"))
    assert markdown_files, "Expected markdown content to be generated"
