"""V3 feed-based banner generator tests."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
from google.api_core import exceptions as google_exceptions

from egregora.agents.banner.image_generation import ImageGenerationRequest, ImageGenerationResult
from egregora_v3.core.types import Author, Document, DocumentType, Entry, Feed
from egregora_v3.engine.banner.feed_generator import (
    BannerGenerationResult,
    BannerTaskEntry,
    FeedBannerGenerator,
)
from egregora_v3.engine.banner.generator import GeminiV3BannerGenerator


@pytest.fixture
def prompts_dir(tmp_path: Path) -> Path:
    """Create a temporary prompts directory with a simple template."""
    prompts = tmp_path / "prompts"
    prompts.mkdir(parents=True)
    (prompts / "banner.jinja").write_text("Banner: {{ post_title }}", encoding="utf-8")
    return prompts


@pytest.fixture
def sample_task_entry() -> Entry:
    """Create a sample entry describing a banner task."""
    return Entry(
        id="task:1",
        title="Amazing AI Blog Post",
        summary="This post discusses the future of artificial intelligence",
        updated=datetime.now(UTC),
        published=datetime.now(UTC),
        authors=[Author(name="Test Author", email="test@example.com")],
        internal_metadata={
            "slug": "amazing-ai-post",
            "language": "pt-BR",
        },
    )


@pytest.fixture
def sample_task_feed(sample_task_entry: Entry) -> Feed:
    """Create a feed with a single banner task."""
    return Feed(
        id="urn:tasks:banner:batch1",
        title="Banner Generation Tasks",
        updated=datetime.now(UTC),
        entries=[sample_task_entry],
        authors=[Author(name="System", email="system@example.com")],
        links=[],
    )


@pytest.fixture
def mock_image_provider():
    """Provider stub returning a fake image."""
    provider = Mock()
    provider.generate.return_value = ImageGenerationResult(
        image_bytes=b"fake-image-data",
        mime_type="image/png",
        debug_text=None,
        error=None,
        error_code=None,
    )
    return provider


class TestBannerTaskEntry:
    """Unit tests for BannerTaskEntry parsing."""

    def test_basic_fields(self, sample_task_entry: Entry):
        task = BannerTaskEntry(sample_task_entry)

        assert task.title == "Amazing AI Blog Post"
        assert task.slug == "amazing-ai-post"
        assert task.language == "pt-BR"

    def test_to_banner_input(self, sample_task_entry: Entry):
        banner_input = BannerTaskEntry(sample_task_entry).to_banner_input()

        assert banner_input.post_title == "Amazing AI Blog Post"
        assert "future of artificial intelligence" in banner_input.post_summary
        assert banner_input.slug == "amazing-ai-post"
        assert banner_input.language == "pt-BR"


class TestBannerGenerationResult:
    """Unit tests for BannerGenerationResult."""

    def test_successful_result(self, sample_task_entry: Entry):
        document = Document.create(
            doc_type=DocumentType.MEDIA,
            title="Banner: Test",
            content="image-data",
        )
        result = BannerGenerationResult(sample_task_entry, document=document)

        assert result.success is True
        assert result.document == document
        assert result.error is None

    def test_failed_result(self, sample_task_entry: Entry):
        result = BannerGenerationResult(
            sample_task_entry,
            error="Generation failed",
            error_code="GENERATION_FAILED",
        )

        assert result.success is False
        assert result.document is None
        assert result.error_code == "GENERATION_FAILED"


class TestFeedBannerGenerator:
    """Integration-style tests for FeedBannerGenerator."""

    def test_generate_from_feed_with_provider(
        self, sample_task_feed: Feed, mock_image_provider, prompts_dir: Path
    ):
        generator = FeedBannerGenerator(provider=mock_image_provider, prompts_dir=prompts_dir)
        result_feed = generator.generate_from_feed(sample_task_feed)

        mock_image_provider.generate.assert_called_once()
        call_args = mock_image_provider.generate.call_args[0][0]
        assert isinstance(call_args, ImageGenerationRequest)
        assert "Amazing AI Blog Post" in call_args.prompt

        assert result_feed.id == f"{sample_task_feed.id}:results"
        assert len(result_feed.entries) == 1
        banner_doc = result_feed.entries[0]
        assert isinstance(banner_doc, Document)


class TestGeminiV3BannerGenerator:
    """Unit tests for the GeminiV3BannerGenerator."""

    def test_generate_propagates_google_api_errors(self):
        """Ensure specific Google API errors are not caught in a generic exception."""
        mock_client = Mock()
        mock_client.models.generate_images.side_effect = google_exceptions.ResourceExhausted(
            "Quota exceeded"
        )

        generator = GeminiV3BannerGenerator(client=mock_client)
        request = ImageGenerationRequest(prompt="test prompt", response_modalities=["IMAGE"])

        with pytest.raises(google_exceptions.ResourceExhausted):
            generator.generate(request)

    def test_generate_from_feed_with_error(self, sample_task_feed: Feed, prompts_dir: Path):
        mock_provider = Mock()
        mock_provider.generate.return_value = ImageGenerationResult(
            image_bytes=None,
            mime_type=None,
            debug_text=None,
            error="API error",
            error_code="API_ERROR",
        )

        generator = FeedBannerGenerator(provider=mock_provider, prompts_dir=prompts_dir)
        result_feed = generator.generate_from_feed(sample_task_feed)

        assert len(result_feed.entries) == 1
        error_doc = result_feed.entries[0]
        assert error_doc.doc_type == DocumentType.NOTE
        assert "API error" in error_doc.content

    def test_generate_from_feed_with_exception(self, sample_task_feed: Feed, prompts_dir: Path):
        mock_provider = Mock()
        mock_provider.generate.side_effect = RuntimeError("Provider crashed")

        generator = FeedBannerGenerator(provider=mock_provider, prompts_dir=prompts_dir)
        with pytest.raises(RuntimeError, match="Provider crashed"):
            generator.generate_from_feed(sample_task_feed)

    def test_metadata_preserved(self, sample_task_feed: Feed, mock_image_provider, prompts_dir: Path):
        generator = FeedBannerGenerator(provider=mock_image_provider, prompts_dir=prompts_dir)
        result_feed = generator.generate_from_feed(sample_task_feed)

        banner_doc = result_feed.entries[0]
        assert banner_doc.internal_metadata is not None
        assert banner_doc.internal_metadata["task_id"] == "task:1"
