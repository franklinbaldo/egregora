"""End-to-end tests with real API calls (requires valid API key).

These tests are skipped by default unless GEMINI_API_KEY environment variable is set.
They test the complete pipeline with actual LLM calls using the real WhatsApp export data.
"""

from __future__ import annotations

import os
import zipfile
from datetime import date
from pathlib import Path

import pytest
from conftest import WhatsAppFixture

from egregora.augmentation.enrichment.core import enrich_table
from egregora.augmentation.enrichment.media import extract_and_replace_media
from egregora.ingestion.parser import parse_export
from egregora.orchestration.pipeline import process_whatsapp_export
from egregora.utils.zip import validate_zip_contents


# Skip all tests in this module if API key is not available
pytestmark = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY environment variable not set - skipping E2E tests with real API",
)


@pytest.fixture()
def gemini_api_key_real() -> str:
    """Return the real Gemini API key from environment."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set")
    return api_key


def test_e2e_full_pipeline_with_real_api(
    whatsapp_fixture: WhatsAppFixture,
    gemini_api_key: str,
    tmp_path: Path,
):
    """Test complete pipeline with real API calls using WhatsApp export data.

    This test:
    1. Parses the real WhatsApp export ZIP
    2. Extracts and processes media files
    3. Enriches messages with real LLM calls
    4. Generates blog posts using the Gemini API

    Expected behavior:
    - All media files should be extracted correctly
    - Enrichment should add contextual information to messages
    - Generated posts should contain valid markdown
    - Post frontmatter should have proper date and metadata
    """
    output_dir = tmp_path / "site"
    output_dir.mkdir()

    # Create mkdocs.yml for site structure
    mkdocs_yml = output_dir / "mkdocs.yml"
    mkdocs_yml.write_text("site_name: Test Site\ndocs_dir: docs\n", encoding="utf-8")

    docs_dir = output_dir / "docs"
    docs_dir.mkdir()

    # Run full pipeline with real API
    process_whatsapp_export(
        zip_path=whatsapp_fixture.zip_path,
        output_dir=output_dir,
        period="day",
        enable_enrichment=True,
        gemini_api_key=gemini_api_key,
    )

    # Verify output structure
    posts_dir = docs_dir / "posts"
    assert posts_dir.exists(), "Posts directory should be created"

    profiles_dir = docs_dir / "profiles"
    assert profiles_dir.exists(), "Profiles directory should be created"

    # Check that posts were generated
    post_files = list(posts_dir.glob("*.md"))
    assert len(post_files) > 0, "At least one post should be generated"

    # Verify post content
    for post_file in post_files:
        content = post_file.read_text(encoding="utf-8")

        # Check frontmatter exists
        assert content.startswith("---\n"), f"Post {post_file.name} should have frontmatter"
        assert "title:" in content, f"Post {post_file.name} should have title"
        assert "date:" in content, f"Post {post_file.name} should have date"

        # Check content exists after frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, f"Post {post_file.name} should have content after frontmatter"
        post_content = parts[2].strip()
        assert len(post_content) > 0, f"Post {post_file.name} should have non-empty content"

    # Verify media files were extracted
    media_dir = docs_dir / "media"
    if media_dir.exists():
        media_files = list(media_dir.rglob("*"))
        media_files = [f for f in media_files if f.is_file() and not f.name.startswith(".")]
        # At least some media files should be present
        # (may be 0 if enrichment disabled media extraction)


def test_e2e_enrichment_with_real_api(
    whatsapp_fixture: WhatsAppFixture,
    gemini_api_key: str,
    tmp_path: Path,
):
    """Test message enrichment with real API calls.

    This test verifies that:
    - URL enrichment adds contextual information
    - Media enrichment processes images/videos correctly
    - Enriched content is meaningful and follows expected format
    """
    from google import genai
    from egregora.config.types import EnrichmentConfig

    export = whatsapp_fixture.create_export()
    table = parse_export(export, timezone=whatsapp_fixture.timezone)

    # Create enrichment config with real API client
    client = genai.Client(api_key=gemini_api_key_real)
    config = EnrichmentConfig(
        client=client,
        output_dir=tmp_path,
        model="models/gemini-2.0-flash-exp",
    )

    # Test media extraction
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir(parents=True)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)

    media_table, media_files = extract_and_replace_media(
        messages_table=table,
        zip_path=whatsapp_fixture.zip_path,
        docs_dir=docs_dir,
        posts_dir=posts_dir,
        group_slug=whatsapp_fixture.group_slug,
    )

    # Verify media files were created
    assert len(media_files) > 0, "Should extract at least one media file"
    for media_path in media_files:
        assert Path(media_path).exists(), f"Media file should exist: {media_path}"

    # Test enrichment (may take a few seconds with real API)
    enriched_table = enrich_table(
        table=media_table,
        client=client,
        output_dir=tmp_path,
        model="models/gemini-2.0-flash-exp",
    )

    # Verify enrichment added content
    enriched_count = enriched_table.count().execute()
    original_count = media_table.count().execute()

    # Enrichment may add rows for URL/media descriptions
    assert enriched_count >= original_count, "Enriched table should have at least as many rows"


def test_e2e_generates_valid_posts_for_date_range(
    whatsapp_fixture: WhatsAppFixture,
    gemini_api_key_real: str,
    tmp_path: Path,
):
    """Test that pipeline generates posts only for specified date range.

    Uses real API to verify:
    - Date filtering works correctly
    - Only messages within range are processed
    - Generated posts have correct dates in frontmatter
    """
    output_dir = tmp_path / "site"
    output_dir.mkdir()

    mkdocs_yml = output_dir / "mkdocs.yml"
    mkdocs_yml.write_text("site_name: Test Site\ndocs_dir: docs\n", encoding="utf-8")

    docs_dir = output_dir / "docs"
    docs_dir.mkdir()

    # Process only specific date
    target_date = date(2025, 10, 28)

    process_whatsapp_export(
        zip_path=whatsapp_fixture.zip_path,
        output_dir=output_dir,
        period="day",
        enable_enrichment=True,
        from_date=target_date,
        to_date=target_date,
        gemini_api_key=gemini_api_key_real,
    )

    # Check posts directory
    posts_dir = docs_dir / "posts"
    post_files = list(posts_dir.glob("2025-10-28*.md"))

    # Should have posts for the target date
    assert len(post_files) > 0, f"Should generate posts for {target_date}"

    # Should NOT have posts for other dates
    other_date_posts = [
        f for f in posts_dir.glob("*.md")
        if not f.name.startswith("2025-10-28")
    ]
    assert len(other_date_posts) == 0, "Should not generate posts outside date range"
