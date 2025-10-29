"""Tests for enricher module, focusing on PII detection."""

# ruff: noqa: E402 - imports after stub installation

import asyncio
import sys
import tempfile
import types
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import ibis

EXPECTED_TEMPERATURE = 0.3
EXPECTED_MEDIA_PARTS = 2

def _install_google_stubs() -> None:  # pragma: no cover - simple fallback
    if "google" in sys.modules:
        return

    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.genai")
    genai_types_module = types.ModuleType("google.genai.types")

    class DummyClient:
        def __init__(self, *_, **__):
            self.aio = types.SimpleNamespace(
                models=types.SimpleNamespace(generate_content=None),
                files=types.SimpleNamespace(upload=None),
            )

    class DummyPart:
        def __init__(self, *, text: str | None = None, file_data: "DummyFileData" | None = None):
            self.text = text
            self.file_data = file_data

    class DummyContent:
        def __init__(self, *, role: str | None = None, parts: list["DummyPart"] | None = None):
            self.role = role
            self.parts = parts or []

    class DummyGenerateContentConfig:
        def __init__(self, *, temperature: float | None = None):
            self.temperature = temperature

    class DummyFileData:
        def __init__(
            self,
            *,
            file_uri: str | None = None,
            mime_type: str | None = None,
            display_name: str | None = None,
        ):
            self.file_uri = file_uri
            self.mime_type = mime_type
            self.display_name = display_name

    class DummyEmbedContentConfig:
        def __init__(self, *_, **__):
            pass

    class DummyTool:
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

    google_module.genai = genai_module
    sys.modules["google"] = google_module
    sys.modules["google.genai"] = genai_module
    sys.modules["google.genai.types"] = genai_types_module


try:  # pragma: no cover - exercised implicitly when dependency is present
    from egregora.cache import EnrichmentCache
    from egregora.config_types import EnrichmentConfig
    from egregora.enricher import (
        build_batch_requests,
        enrich_dataframe,
        enrich_media,
        map_batch_results,
        replace_media_mentions,
    )
    from egregora.gemini_batch import BatchPromptResult
except ModuleNotFoundError:  # pragma: no cover - optional dependency missing
    _install_google_stubs()
    from egregora.cache import EnrichmentCache
    from egregora.config_types import EnrichmentConfig
    from egregora.enricher import (
        build_batch_requests,
        enrich_dataframe,
        enrich_media,
        map_batch_results,
        replace_media_mentions,
    )
    from egregora.gemini_batch import BatchPromptResult


def test_build_batch_requests_for_text_prompts():
    records = [
        {
            "tag": "url:test",
            "prompt": "Describe the link",
        }
    ]

    requests = build_batch_requests(records, model="text-model")

    assert len(requests) == 1
    request = requests[0]
    assert request.model == "text-model"
    assert request.tag == "url:test"
    assert request.contents[0].role == "user"
    assert request.contents[0].parts[0].text == "Describe the link"
    assert request.config is not None
    assert request.config.temperature == EXPECTED_TEMPERATURE


def test_build_batch_requests_for_media_prompts():
    records = [
        {
            "tag": "media:test",
            "prompt": "Describe the file",
            "file_uri": "gs://media/test.png",
            "mime_type": "image/png",
        }
    ]

    requests = build_batch_requests(records, model="vision-model", include_file=True)

    assert len(requests) == 1
    request = requests[0]
    assert request.model == "vision-model"
    assert request.tag == "media:test"
    assert request.contents[0].parts[0].text == "Describe the file"
    assert len(request.contents[0].parts) == EXPECTED_MEDIA_PARTS
    file_part = request.contents[0].parts[1]
    assert file_part.file_data.file_uri == "gs://media/test.png"
    assert file_part.file_data.mime_type == "image/png"
    assert request.config is None


def test_map_batch_results_includes_none_tags():
    responses = [
        BatchPromptResult(tag="alpha", response=MagicMock()),
        BatchPromptResult(tag=None, response=MagicMock()),
    ]

    result_map = map_batch_results(responses)

    assert result_map["alpha"] is responses[0]
    assert result_map[None] is responses[1]


def test_enrich_media_with_pii_detection():
    """Test that media with PII is deleted but description is kept."""
    async def run() -> None:
        # Create temporary test media file
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            test_media = output_dir / "test_id_card.jpg"
            test_media.write_bytes(b"fake image data")

            # Mock configuration
            mock_config = EnrichmentConfig(
                client=Mock(),
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

            upload_fn = AsyncMock()
            generate_fn = AsyncMock()

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
                    upload_fn=upload_fn,
                    generate_content_fn=generate_fn,
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

    asyncio.run(run())


def test_enrich_media_without_pii():
    """Test normal media enrichment when no PII detected."""
    async def run() -> None:
        # Create temporary test media file
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            test_media = output_dir / "test_landscape.jpg"
            test_media.write_bytes(b"fake image data")

            # Mock configuration
            mock_config = EnrichmentConfig(
                client=Mock(),
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

            upload_fn = AsyncMock()
            generate_fn = AsyncMock()

            with patch("egregora.enricher.call_with_retries", new_callable=AsyncMock) as mock_retry:
                mock_retry.side_effect = [mock_uploaded_file, mock_response]

                # Run enrichment
                result = await enrich_media(
                    file_path=test_media,
                    original_message="Nice view",
                    sender_uuid="test123",
                    timestamp=MagicMock(strftime=lambda x: "2024-01-01" if "Y" in x else "12:00"),
                    config=mock_config,
                    upload_fn=upload_fn,
                    generate_content_fn=generate_fn,
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

    asyncio.run(run())


def test_replace_media_mentions_deleted_file():
    """Test that deleted media shows privacy notice."""
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = Path(tmpdir)
        posts_dir = docs_dir / "posts"
        posts_dir.mkdir(parents=True, exist_ok=True)

        # Create a media mapping pointing to a non-existent (deleted) file
        deleted_file = docs_dir / "media" / "images" / "deleted_file.jpg"
        media_mapping = {"IMG-123.jpg": deleted_file}

        text = "See this IMG-123.jpg (file attached)"

        # Run replacement
        result = replace_media_mentions(text, media_mapping, docs_dir, posts_dir)

        # Assertions
        assert "[Media removed: privacy protection]" in result
        assert "IMG-123.jpg" not in result


def test_replace_media_mentions_existing_file():
    """Test that existing media gets proper markdown links."""
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = Path(tmpdir)
        posts_dir = docs_dir / "posts"
        posts_dir.mkdir(parents=True, exist_ok=True)

        # Create actual media file
        media_dir = docs_dir / "media" / "images"
        media_dir.mkdir(parents=True)
        existing_file = media_dir / "abc123.jpg"
        existing_file.write_bytes(b"test image")

        media_mapping = {"IMG-123.jpg": existing_file}

        text = "See this IMG-123.jpg (file attached)"

        # Run replacement
        result = replace_media_mentions(text, media_mapping, docs_dir, posts_dir)

        # Assertions
        assert "![Image]" in result
        assert "../media/images/abc123.jpg" in result
        assert "IMG-123.jpg (file attached)" not in result


def test_enrich_dataframe_refreshes_deleted_media_mentions():
    """When media is deleted for PII, messages should show privacy notice."""
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = Path(tmpdir)
        posts_dir = docs_dir / "posts"
        posts_dir.mkdir(parents=True, exist_ok=True)

        media_dir = docs_dir / "media" / "images"
        media_dir.mkdir(parents=True)
        media_file = media_dir / "abc123.jpg"
        media_file.write_bytes(b"test image")

        media_mapping = {"IMG-123.jpg": media_file}

        original_text = "See this IMG-123.jpg (file attached)"
        replaced_text = replace_media_mentions(original_text, media_mapping, docs_dir, posts_dir)

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

        text_batch_client = MagicMock()
        text_batch_client.generate_content.return_value = []

        vision_batch_client = MagicMock()
        vision_batch_client.upload_file.return_value = types.SimpleNamespace(
            uri="test://file", mime_type="image/jpeg"
        )

        def mock_generate_content(requests, **_kwargs):
            results = []
            for request in requests:
                results.append(
                    BatchPromptResult(
                        tag=request.tag,
                        response=types.SimpleNamespace(
                            text="PII_DETECTED\n[Media removed: privacy protection]"
                        ),
                        error=None,
                    )
                )
            return results

        vision_batch_client.generate_content.side_effect = mock_generate_content

        cache_dir = docs_dir / "cache"
        cache = EnrichmentCache(cache_dir)

        result_df = enrich_dataframe(
            df=df,
            media_mapping=media_mapping,
            text_batch_client=text_batch_client,
            vision_batch_client=vision_batch_client,
            cache=cache,
            docs_dir=docs_dir,
            posts_dir=posts_dir,
            enable_url=False,
            enable_media=True,
            max_enrichments=5,
        )

        original_rows = result_df.filter(result_df.author != "egregora")
        assert original_rows.count().execute() == 1
        message_value = original_rows.message.execute().iloc[0]
        assert "[Media removed: privacy protection]" in message_value
        assert "![Image]" not in message_value
