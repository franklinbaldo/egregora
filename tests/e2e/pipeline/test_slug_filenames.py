import pytest
from pathlib import Path
import json
from unittest.mock import MagicMock
import uuid

from egregora.orchestration.pipelines.write import WhatsAppProcessOptions, process_whatsapp_export
from egregora.output_adapters.mkdocs import MkDocsAdapter
from egregora.output_adapters.mkdocs.paths import derive_mkdocs_paths
from egregora.agents.enricher import EnrichmentWorker

@pytest.fixture
def pipeline_setup_minimal(whatsapp_fixture):
    """Bundle common pipeline fixtures to reduce test parameters."""
    return {
        "whatsapp_fixture": whatsapp_fixture,
        "gemini_api_key": "test-key",
    }

@pytest.mark.e2e
def test_media_filename_uses_llm_slug(pipeline_setup_minimal, tmp_path, mocker):
    """Verify that media files are saved using the slug provided by the LLM."""
    
    # Setup output directory
    site_root = tmp_path / "site"
    site_root.mkdir()

    # Scaffolding
    adapter = MkDocsAdapter()
    adapter.scaffold_site(site_root, site_name="Test Slug Site")

    # Mock parameters
    target_slug = "custom-slug-from-llm"
    
    # We will mock the method that performs the actual LLM call and result parsing
    # EnrichmentWorker._enrich_media_batch is the main entry point for media enrichment
    orig_method = EnrichmentWorker._enrich_media_batch
    
    def mock_enrich_media_batch(self, tasks):
        # Instead of calling LLM, we manually construct the results
        # This bypasses the need to mock the genai client
        from egregora.agents.enricher import _normalize_slug
        
        results_count = 0
        for task in tasks:
            # Prepare a mock payload that looks like it came from _parse_media_result
            payload = task["_parsed_payload"]
            slug_value = _normalize_slug(target_slug, payload["filename"])
            markdown = "# Mocked Enrichment\n\nContent goes here."
            
            # Use the actual _persist_media_results logic
            # This is what we are REALLY testing (how it uses slug_value to name files)
            self._persist_media_results([(payload, slug_value, markdown)], task)
            results_count += 1
            
        return results_count

    mocker.patch.object(EnrichmentWorker, "_enrich_media_batch", autospec=True, side_effect=mock_enrich_media_batch)

    options = WhatsAppProcessOptions(
        output_dir=site_root,
        timezone=pipeline_setup_minimal["whatsapp_fixture"].timezone,
        gemini_api_key="fake-key",
        enable_enrichment=True,
    )

    # Run pipeline
    process_whatsapp_export(
        pipeline_setup_minimal["whatsapp_fixture"].zip_path,
        options=options,
    )

    # Resolve paths
    site_paths = derive_mkdocs_paths(site_root)
    
    # Check all files recursively
    all_files = list(site_root.rglob("*"))
    print(f"All generated files: {[f.relative_to(site_root) for f in all_files]}")

    expected_file = None
    for f in all_files:
        if f.stem == target_slug:
            expected_file = f
            break
    
    assert expected_file is not None, f"A file with stem '{target_slug}' should exist in the output"
    assert expected_file.suffix == ".jpg", f"The file should have the original extension .jpg, got {expected_file.suffix}"
    
    # Verify it's in the media directory
    assert "media" in expected_file.parts
    # It should also be in the 'images' subdirectory based on .jpg
    assert "images" in expected_file.parts

    print(f"SUCCESS: Found slug-based media file at {expected_file.relative_to(site_root)}")
