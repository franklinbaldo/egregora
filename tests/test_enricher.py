"""Tests for enricher module, focusing on PII detection."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from egregora.config_types import EnrichmentConfig
from egregora.enricher import enrich_media, replace_media_mentions


@pytest.mark.asyncio
async def test_enrich_media_with_pii_detection():
    """Test that media with PII is deleted but description is kept."""
    # Create temporary test media file
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        test_media = output_dir / "test_id_card.jpg"
        test_media.write_bytes(b"fake image data")

        # Mock configuration
        mock_client = Mock()
        mock_config = EnrichmentConfig(
            client=mock_client,
            output_dir=output_dir,
            model="test-model",
        )

        # Mock the response with PII code word
        mock_response = MagicMock()
        mock_response.text = """PII_DETECTED

# Enrichment: test_id_card.jpg

## Metadata
- **Date:** 2024-01-01
- **Time:** 12:00
- **Sender:** test123
- **Media Type:** image
- **File:** media/images/test.jpg

## Original Message
> Check this ID

## Description
This image shows a person holding an identification document in an indoor setting.

[This media contained personal information which has been redacted for privacy protection]
"""

        # Mock the Gemini API calls
        mock_uploaded_file = MagicMock()
        mock_uploaded_file.uri = "test://file"
        mock_uploaded_file.mime_type = "image/jpeg"

        with patch("egregora.enricher.call_with_retries", new_callable=AsyncMock) as mock_retry:
            # First call is for file upload, second is for generate_content
            mock_retry.side_effect = [mock_uploaded_file, mock_response]

            # Run enrichment
            result = await enrich_media(
                file_path=test_media,
                original_message="Check this ID",
                sender_uuid="test123",
                timestamp=MagicMock(strftime=lambda x: "2024-01-01" if "Y" in x else "12:00"),
                config=mock_config,
            )

            # Assertions
            assert not test_media.exists(), "Media file should be deleted when PII detected"
            assert result  # Enrichment path should still be returned

            # Check that enrichment was saved
            enrichment_path = Path(result)
            assert enrichment_path.exists(), "Enrichment file should be saved"

            # Check that code word was removed from saved enrichment
            enrichment_text = enrichment_path.read_text()
            assert "PII_DETECTED" not in enrichment_text, "Code word should be removed"
            assert "redacted for privacy protection" in enrichment_text.lower()


@pytest.mark.asyncio
async def test_enrich_media_without_pii():
    """Test normal media enrichment when no PII detected."""
    # Create temporary test media file
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        test_media = output_dir / "test_landscape.jpg"
        test_media.write_bytes(b"fake image data")

        # Mock configuration
        mock_client = Mock()
        mock_config = EnrichmentConfig(
            client=mock_client,
            output_dir=output_dir,
            model="test-model",
        )

        # Mock the response WITHOUT PII code word
        mock_response = MagicMock()
        mock_response.text = """# Enrichment: test_landscape.jpg

## Metadata
- **Date:** 2024-01-01
- **Time:** 12:00
- **Sender:** test123
- **Media Type:** image
- **File:** media/images/test.jpg

## Original Message
> Nice view

## Description
This is a beautiful landscape photo showing mountains and valleys with dramatic lighting.
The composition features a wide vista with layers of mountain ranges receding into the distance.
"""

        # Mock the Gemini API calls
        mock_uploaded_file = MagicMock()
        mock_uploaded_file.uri = "test://file"
        mock_uploaded_file.mime_type = "image/jpeg"

        with patch("egregora.enricher.call_with_retries", new_callable=AsyncMock) as mock_retry:
            mock_retry.side_effect = [mock_uploaded_file, mock_response]

            # Run enrichment
            result = await enrich_media(
                file_path=test_media,
                original_message="Nice view",
                sender_uuid="test123",
                timestamp=MagicMock(strftime=lambda x: "2024-01-01" if "Y" in x else "12:00"),
                config=mock_config,
            )

            # Assertions
            assert test_media.exists(), "Media file should NOT be deleted when no PII"
            assert result

            # Check enrichment content
            enrichment_path = Path(result)
            assert enrichment_path.exists()
            enrichment_text = enrichment_path.read_text()
            assert "PII_DETECTED" not in enrichment_text
            assert "landscape" in enrichment_text.lower()


def test_replace_media_mentions_deleted_file():
    """Test that deleted media shows privacy notice."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Create a media mapping pointing to a non-existent (deleted) file
        deleted_file = output_dir / "deleted_file.jpg"
        media_mapping = {"IMG-123.jpg": deleted_file}

        text = "See this IMG-123.jpg (file attached)"

        # Run replacement
        result = replace_media_mentions(text, media_mapping, output_dir)

        # Assertions
        assert "[Media removed: privacy protection]" in result
        assert "IMG-123.jpg" not in result


def test_replace_media_mentions_existing_file():
    """Test that existing media gets proper markdown links."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Create actual media file
        media_dir = output_dir / "media" / "images"
        media_dir.mkdir(parents=True)
        existing_file = media_dir / "abc123.jpg"
        existing_file.write_bytes(b"test image")

        media_mapping = {"IMG-123.jpg": existing_file}

        text = "See this IMG-123.jpg (file attached)"

        # Run replacement
        result = replace_media_mentions(text, media_mapping, output_dir)

        # Assertions
        assert "![Image]" in result
        assert "media/images/abc123.jpg" in result
        assert "IMG-123.jpg (file attached)" not in result
