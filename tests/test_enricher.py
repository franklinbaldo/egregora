"""Tests for enricher module, focusing on PII detection."""

import sys
import tempfile
import types
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Provide minimal google genai stubs so egregora package can import without optional deps.
if "google" not in sys.modules:
    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.genai")
    genai_types_module = types.ModuleType("google.genai.types")

    class DummyClient:  # pragma: no cover - simple stub
        def __init__(self, *_, **__):
            self.aio = types.SimpleNamespace(
                models=types.SimpleNamespace(generate_content=None),
                files=types.SimpleNamespace(upload=None),
            )

    class DummyPart:  # pragma: no cover - simple stub
        def __init__(self, *_, **__):
            pass

    class DummyContent:  # pragma: no cover - simple stub
        def __init__(self, *_, **__):
            pass

    class DummyGenerateContentConfig:  # pragma: no cover - simple stub
        def __init__(self, *_, **__):
            pass

    class DummyFileData:  # pragma: no cover - simple stub
        def __init__(self, *_, **__):
            pass

    class DummyEmbedContentConfig:  # pragma: no cover - simple stub
        def __init__(self, *_, **__):
            pass

    class DummyTool:  # pragma: no cover - simple stub
        def __init__(self, *_, **__):
            pass

    genai_module.Client = DummyClient
    genai_module.types = genai_types_module
    genai_types_module.Part = DummyPart
    genai_types_module.Content = DummyContent
    genai_types_module.GenerateContentConfig = DummyGenerateContentConfig
    genai_types_module.FileData = DummyFileData
    genai_types_module.EmbedContentConfig = DummyEmbedContentConfig
    genai_types_module.Tool = DummyTool

    sys.modules["google"] = google_module
    sys.modules["google.genai"] = genai_module
    sys.modules["google.genai.types"] = genai_types_module
    google_module.genai = genai_module

import ibis

from egregora.config_types import EnrichmentConfig
from egregora.enricher import enrich_dataframe, enrich_media, replace_media_mentions


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


@pytest.mark.asyncio
async def test_enrich_dataframe_refreshes_deleted_media_mentions():
    """When media is deleted for PII, messages should show privacy notice."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        media_dir = output_dir / "media" / "images"
        media_dir.mkdir(parents=True)
        media_file = media_dir / "abc123.jpg"
        media_file.write_bytes(b"test image")

        media_mapping = {"IMG-123.jpg": media_file}

        original_text = "See this IMG-123.jpg (file attached)"
        replaced_text = replace_media_mentions(original_text, media_mapping, output_dir)

        df = ibis.memtable(
            {
                "timestamp": [datetime(2024, 1, 1, 12, 0, 0)],
                "date": [date(2024, 1, 1)],
                "author": ["alice"],
                "message": [replaced_text],
                "original_line": [""],
                "tagged_line": [""],
            }
        )

        async def mock_enrich_media(**kwargs):  # type: ignore[override]
            if media_file.exists():
                media_file.unlink()
            return str(output_dir / "media" / "enrichments" / "dummy.md")

        with patch("egregora.enricher.enrich_media", side_effect=mock_enrich_media):
            result_df = await enrich_dataframe(
                df=df,
                media_mapping=media_mapping,
                client=MagicMock(),
                output_dir=output_dir,
                enable_url=False,
                enable_media=True,
                max_enrichments=5,
            )

        original_rows = result_df.filter(result_df.author != "egregora")
        assert original_rows.count().execute() == 1
        message_value = original_rows.message.execute().iloc[0]
        assert "[Media removed: privacy protection]" in message_value
        assert "![Image]" not in message_value
