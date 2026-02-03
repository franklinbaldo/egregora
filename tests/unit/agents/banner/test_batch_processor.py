"""Tests for the banner batch pipeline."""

from unittest.mock import Mock

import pytest

from egregora.agents.banner.agent import BannerOutput
from egregora.agents.banner.batch_processor import (
    BannerBatchProcessor,
    BannerGenerationResult,
    BannerTaskEntry,
)
from egregora.agents.banner.exceptions import BannerGenerationError
from egregora.agents.banner.image_generation import (
    ImageGenerationRequest,
    ImageGenerationResult,
)
from egregora.data_primitives.document import Document, DocumentType


@pytest.fixture
def sample_task_entry() -> BannerTaskEntry:
    """Create a sample banner task entry."""
    return BannerTaskEntry(
        task_id="task:1",
        title="Amazing AI Blog Post",
        summary="This post discusses the future of artificial intelligence",
        slug="amazing-ai-post",
        language="pt-BR",
    )


@pytest.fixture
def mock_image_provider():
    """Create a mock image generation provider."""
    provider = Mock()
    provider.generate.return_value = ImageGenerationResult(
        image_bytes=b"fake-image-data",
        mime_type="image/png",
        debug_text=None,
    )
    return provider


class TestBannerTaskEntry:
    """Tests for BannerTaskEntry."""

    def test_to_banner_input(self, sample_task_entry: BannerTaskEntry):
        """Ensure tasks convert to BannerInput payloads."""
        banner_input = sample_task_entry.to_banner_input()

        assert banner_input.post_title == "Amazing AI Blog Post"
        assert "future of artificial intelligence" in banner_input.post_summary
        assert banner_input.slug == "amazing-ai-post"
        assert banner_input.language == "pt-BR"


class TestBannerGenerationResult:
    """Tests for BannerGenerationResult."""

    def test_successful_result(self, sample_task_entry: BannerTaskEntry):
        """Test successful generation result."""
        document = Document(
            content=b"image-data",
            type=DocumentType.MEDIA,
            metadata={"slug": "test"},
        )
        result = BannerGenerationResult(sample_task_entry, document=document)

        assert result.success is True
        assert result.document == document
        assert result.error is None
        assert result.error_code is None

    def test_failed_result(self, sample_task_entry: BannerTaskEntry):
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


class TestBannerBatchProcessor:
    """Tests for BannerBatchProcessor."""

    def test_process_tasks_with_provider(self, sample_task_entry: BannerTaskEntry, mock_image_provider):
        """Process tasks using an injected provider."""
        processor = BannerBatchProcessor(provider=mock_image_provider)
        results = processor.process_tasks([sample_task_entry])

        assert len(results) == 1
        assert results[0].success is True
        assert isinstance(results[0].document, Document)

        mock_image_provider.generate.assert_called_once()
        call_args = mock_image_provider.generate.call_args[0][0]
        assert isinstance(call_args, ImageGenerationRequest)
        assert "Amazing AI Blog Post" in call_args.prompt

    def test_process_tasks_with_error(self, sample_task_entry: BannerTaskEntry):
        """Provider raises BannerGenerationError."""
        mock_provider = Mock()
        mock_provider.generate.side_effect = BannerGenerationError("API error")

        processor = BannerBatchProcessor(provider=mock_provider)
        results = processor.process_tasks([sample_task_entry])

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].error == "API error"
        assert results[0].error_code == "BannerGenerationError"

    def test_process_tasks_with_exception(self, sample_task_entry: BannerTaskEntry):
        """Provider raises runtime error."""
        mock_provider = Mock()
        mock_provider.generate.side_effect = RuntimeError("Provider crashed")

        processor = BannerBatchProcessor(provider=mock_provider)
        results = processor.process_tasks([sample_task_entry])

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].error == "Provider crashed"
        assert results[0].error_code == "UNEXPECTED_ERROR"

    def test_generate_multiple_entries(self, mock_image_provider):
        """Process multiple banner tasks sequentially."""
        tasks = [
            BannerTaskEntry(
                task_id=f"task:{i}",
                title=f"Post {i}",
                summary=f"Summary {i}",
                slug=f"post-{i}",
            )
            for i in range(3)
        ]

        processor = BannerBatchProcessor(provider=mock_image_provider)
        results = processor.process_tasks(tasks)

        assert len(results) == 3
        assert mock_image_provider.generate.call_count == 3
        assert all(result.success for result in results)

    def test_batch_generation_fallback(self, sample_task_entry: BannerTaskEntry):
        """Batch mode falls back for non-Gemini providers."""
        mock_provider = Mock()
        mock_provider.generate.return_value = ImageGenerationResult(
            image_bytes=b"fake-image",
            mime_type="image/png",
            debug_text=None,
        )

        processor = BannerBatchProcessor(provider=mock_provider)
        results = processor.process_tasks([sample_task_entry], batch_mode=True)

        assert len(results) == 1
        mock_provider.generate.assert_called_once()

    def test_preserve_task_metadata(self, sample_task_entry: BannerTaskEntry, mock_image_provider):
        """Ensure generated documents retain task metadata."""
        processor = BannerBatchProcessor(provider=mock_image_provider)
        results = processor.process_tasks([sample_task_entry])

        document = results[0].document
        assert document is not None
        assert document.metadata["task_id"] == sample_task_entry.task_id
        assert document.metadata["slug"] == sample_task_entry.slug
        assert document.metadata["language"] == sample_task_entry.language

    def test_default_generation_path(
        self, sample_task_entry: BannerTaskEntry, monkeypatch: pytest.MonkeyPatch
    ):
        """Use the synchronous generate_banner implementation."""

        def fake_generate_banner(**_: str):
            return BannerOutput(
                document=Document(
                    content=b"image-bytes",
                    type=DocumentType.MEDIA,
                    metadata={"mime_type": "image/png"},
                )
            )

        monkeypatch.setattr("egregora.agents.banner.batch_processor.generate_banner", fake_generate_banner)

        processor = BannerBatchProcessor(provider=None)
        results = processor.process_tasks([sample_task_entry])

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].document is not None
        assert results[0].document.metadata["task_id"] == sample_task_entry.task_id

    def test_process_tasks_with_none_provider_result(self, sample_task_entry: BannerTaskEntry):
        """Provider returns None without raising exception (fallback case)."""
        mock_provider = Mock()
        mock_provider.generate.return_value = None  # Simulate unexpected None return

        processor = BannerBatchProcessor(provider=mock_provider)
        results = processor.process_tasks([sample_task_entry])

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].error == "Provider returned None without raising exception"
        assert results[0].error_code == "BannerError"
