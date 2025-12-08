"""Tests for feed-based banner generator."""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from egregora.agents.banner.feed_generator import (
    BannerGenerationResult,
    BannerTaskEntry,
    FeedBannerGenerator,
)
from egregora.agents.banner.image_generation import (
    ImageGenerationRequest,
    ImageGenerationResult,
)
from egregora_v3.core.types import Author, Document, DocumentType, Entry, Feed


@pytest.fixture
def sample_task_entry() -> Entry:
    """Create a sample task entry."""
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
    """Create a sample task feed."""
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
    """Create a mock image generation provider."""
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
    """Tests for BannerTaskEntry."""

    def test_extract_basic_fields(self, sample_task_entry: Entry):
        """Test extracting basic fields from entry."""
        task = BannerTaskEntry(sample_task_entry)

        assert task.title == "Amazing AI Blog Post"
        assert task.summary == "This post discusses the future of artificial intelligence"
        assert task.slug == "amazing-ai-post"
        assert task.language == "pt-BR"

    def test_extract_missing_summary(self):
        """Test entry with missing summary."""
        entry = Entry(
            id="task:2",
            title="No Summary Post",
            summary=None,
            updated=datetime.now(UTC),
        )
        task = BannerTaskEntry(entry)

        assert task.title == "No Summary Post"
        assert task.summary == ""

    def test_extract_default_language(self):
        """Test entry with missing language defaults to pt-BR."""
        entry = Entry(
            id="task:3",
            title="Default Language Post",
            updated=datetime.now(UTC),
            internal_metadata={"slug": "test"},
        )
        task = BannerTaskEntry(entry)

        assert task.language == "pt-BR"

    def test_extract_custom_language(self):
        """Test entry with custom language."""
        entry = Entry(
            id="task:4",
            title="English Post",
            updated=datetime.now(UTC),
            internal_metadata={"slug": "test", "language": "en-US"},
        )
        task = BannerTaskEntry(entry)

        assert task.language == "en-US"

    def test_to_banner_input(self, sample_task_entry: Entry):
        """Test conversion to BannerInput."""
        task = BannerTaskEntry(sample_task_entry)
        banner_input = task.to_banner_input()

        assert banner_input.post_title == "Amazing AI Blog Post"
        assert banner_input.post_summary == "This post discusses the future of artificial intelligence"
        assert banner_input.slug == "amazing-ai-post"
        assert banner_input.language == "pt-BR"


class TestBannerGenerationResult:
    """Tests for BannerGenerationResult."""

    def test_successful_result(self, sample_task_entry: Entry):
        """Test successful generation result."""
        document = Document.create(
            doc_type=DocumentType.MEDIA,
            title="Banner: Test",
            content="image-data",
        )
        result = BannerGenerationResult(sample_task_entry, document=document)

        assert result.success is True
        assert result.document == document
        assert result.error is None
        assert result.error_code is None

    def test_failed_result(self, sample_task_entry: Entry):
        """Test failed generation result."""
        result = BannerGenerationResult(
            sample_task_entry,
            error="Generation failed",
            error_code="GENERATION_FAILED",
        )

        assert result.success is False
        assert result.document is None
        assert result.error == "Generation failed"
        assert result.error_code == "GENERATION_FAILED"


class TestFeedBannerGenerator:
    """Tests for FeedBannerGenerator."""

    def test_generate_from_feed_with_provider(self, sample_task_feed: Feed, mock_image_provider):
        """Test generating banners from feed using a provider."""
        generator = FeedBannerGenerator(provider=mock_image_provider)
        result_feed = generator.generate_from_feed(sample_task_feed)

        # Verify provider was called
        mock_image_provider.generate.assert_called_once()
        call_args = mock_image_provider.generate.call_args[0][0]
        assert isinstance(call_args, ImageGenerationRequest)
        assert "Amazing AI Blog Post" in call_args.prompt

        # Verify result feed
        assert result_feed.id == f"{sample_task_feed.id}:results"
        assert result_feed.title == f"{sample_task_feed.title} - Results"
        assert len(result_feed.entries) == 1

        # Verify generated document
        banner_doc = result_feed.entries[0]
        assert isinstance(banner_doc, Document)
        assert banner_doc.doc_type == DocumentType.MEDIA
        assert "Banner:" in banner_doc.title
        assert banner_doc.internal_metadata is not None
        assert "task_id" in banner_doc.internal_metadata

    def test_generate_from_feed_with_error(self, sample_task_feed: Feed):
        """Test generating banners when provider fails."""
        mock_provider = Mock()
        mock_provider.generate.return_value = ImageGenerationResult(
            image_bytes=None,
            mime_type=None,
            debug_text=None,
            error="API error",
            error_code="API_ERROR",
        )

        generator = FeedBannerGenerator(provider=mock_provider)
        result_feed = generator.generate_from_feed(sample_task_feed)

        # Verify error document was created
        assert len(result_feed.entries) == 1
        error_doc = result_feed.entries[0]
        assert isinstance(error_doc, Document)
        assert error_doc.doc_type == DocumentType.NOTE
        assert "Error:" in error_doc.title
        assert "API error" in error_doc.content

    def test_generate_from_feed_with_exception(self, sample_task_feed: Feed):
        """Test generating banners when provider raises exception."""
        mock_provider = Mock()
        mock_provider.generate.side_effect = RuntimeError("Provider crashed")

        generator = FeedBannerGenerator(provider=mock_provider)
        result_feed = generator.generate_from_feed(sample_task_feed)

        # Verify error document was created
        assert len(result_feed.entries) == 1
        error_doc = result_feed.entries[0]
        assert isinstance(error_doc, Document)
        assert "Error:" in error_doc.title
        assert "Provider crashed" in error_doc.content

    def test_generate_multiple_entries(self, mock_image_provider):
        """Test generating banners for multiple task entries."""
        feed = Feed(
            id="urn:tasks:banner:multi",
            title="Multiple Tasks",
            updated=datetime.now(UTC),
            entries=[
                Entry(
                    id=f"task:{i}",
                    title=f"Post {i}",
                    summary=f"Summary {i}",
                    updated=datetime.now(UTC),
                    internal_metadata={"slug": f"post-{i}"},
                )
                for i in range(3)
            ],
            authors=[],
            links=[],
        )

        generator = FeedBannerGenerator(provider=mock_image_provider)
        result_feed = generator.generate_from_feed(feed)

        # Verify all entries were processed
        assert len(result_feed.entries) == 3
        assert mock_image_provider.generate.call_count == 3

        # Verify each document
        for i, doc in enumerate(result_feed.entries):
            assert isinstance(doc, Document)
            assert doc.doc_type == DocumentType.MEDIA
            assert doc.internal_metadata is not None
            assert doc.internal_metadata["task_id"] == f"task:{i}"

    def test_sequential_generation_mode(self, sample_task_feed: Feed, mock_image_provider):
        """Test sequential generation mode (default)."""
        generator = FeedBannerGenerator(provider=mock_image_provider)
        result_feed = generator.generate_from_feed(sample_task_feed, batch_mode=False)

        assert len(result_feed.entries) == 1
        mock_image_provider.generate.assert_called_once()

    def test_batch_generation_fallback(self, sample_task_feed: Feed):
        """Test batch mode fallback for non-Gemini providers."""
        # Mock provider that's not GeminiImageGenerationProvider
        mock_provider = Mock()
        mock_provider.generate.return_value = ImageGenerationResult(
            image_bytes=b"fake-image",
            mime_type="image/png",
            debug_text=None,
            error=None,
            error_code=None,
        )

        generator = FeedBannerGenerator(provider=mock_provider)
        result_feed = generator.generate_from_feed(sample_task_feed, batch_mode=True)

        # Should fallback to sequential
        assert len(result_feed.entries) == 1
        mock_provider.generate.assert_called_once()

    def test_preserve_task_metadata(self, sample_task_feed: Feed, mock_image_provider):
        """Test that task metadata is preserved in output documents."""
        generator = FeedBannerGenerator(provider=mock_image_provider)
        result_feed = generator.generate_from_feed(sample_task_feed)

        banner_doc = result_feed.entries[0]
        assert banner_doc.internal_metadata is not None
        assert banner_doc.internal_metadata["task_id"] == "task:1"
        assert "generated_at" in banner_doc.internal_metadata

    def test_feed_metadata_preservation(self, sample_task_feed: Feed, mock_image_provider):
        """Test that feed metadata is preserved in output feed."""
        generator = FeedBannerGenerator(provider=mock_image_provider)
        result_feed = generator.generate_from_feed(sample_task_feed)

        assert result_feed.authors == sample_task_feed.authors
        assert result_feed.id.startswith(sample_task_feed.id)
        assert sample_task_feed.title in result_feed.title
