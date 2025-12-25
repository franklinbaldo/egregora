"""Tests for EnricherAgent.

EnricherAgent processes feed entries to add enrichments:
- Generates descriptions for media (images, audio, video)
- Adds metadata and context
- Returns enriched feed with updated entries
"""

from datetime import UTC, datetime

import ibis
import pytest

from egregora_v3.core.catalog import ContentLibrary
from egregora_v3.core.context import PipelineContext
from egregora_v3.core.types import Entry, Link
from egregora_v3.engine.agents.enricher import EnricherAgent, EnrichmentResult
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository


@pytest.fixture
def content_library() -> ContentLibrary:
    """Create a content library for testing using in-memory DuckDB."""
    # Use in-memory DuckDB repositories for testing
    conn = ibis.duckdb.connect(":memory:")
    repo = DuckDBDocumentRepository(conn)
    repo.initialize()

    return ContentLibrary(
        posts=repo,
        media=repo,
        profiles=repo,
        journal=repo,
        enrichments=repo,
    )


@pytest.fixture
def pipeline_context(content_library: ContentLibrary) -> PipelineContext:
    """Create a basic pipeline context for testing."""
    return PipelineContext(
        library=content_library,
        run_id="test-run-enricher",
        metadata={"test": True},
    )


@pytest.fixture
def entry_with_image() -> Entry:
    """Create an entry with an image enclosure."""
    return Entry(
        id="test-entry-1",
        title="Photo from vacation",
        content="",  # Empty content - needs enrichment
        updated=datetime.now(UTC),
        links=[
            Link(
                rel="enclosure",
                href="http://example.com/photo.jpg",
                type="image/jpeg",
                length=245760,
            )
        ],
    )


@pytest.fixture
def entry_without_media() -> Entry:
    """Create an entry without media."""
    return Entry(
        id="test-entry-2",
        title="Text-only entry",
        content="This is a regular text entry.",
        updated=datetime.now(UTC),
    )


@pytest.fixture
def entry_with_existing_content() -> Entry:
    """Create an entry with existing content and media."""
    return Entry(
        id="test-entry-3",
        title="Photo with description",
        content="Beautiful sunset at the beach",
        updated=datetime.now(UTC),
        links=[
            Link(
                rel="enclosure",
                href="http://example.com/sunset.jpg",
                type="image/jpeg",
            )
        ],
    )


class TestEnricherAgentBasics:
    """Test basic EnricherAgent functionality."""

    def test_enricher_agent_initializes_with_test_model(self) -> None:
        """EnricherAgent should initialize with TestModel for testing."""
        agent = EnricherAgent(model="test")
        assert agent.model_name == "test"

    @pytest.mark.asyncio
    async def test_enricher_processes_entry_with_image(
        self,
        entry_with_image: Entry,
        pipeline_context: PipelineContext,
    ) -> None:
        """EnricherAgent should return an EnrichmentResult for an entry with an image."""
        agent = EnricherAgent(model="test")
        result = await agent.enrich(entry_with_image, pipeline_context)

        assert isinstance(result, EnrichmentResult)
        assert result.description
        assert "A beautiful sunset" in result.description

    @pytest.mark.asyncio
    async def test_enricher_skips_entry_without_media(
        self,
        entry_without_media: Entry,
        pipeline_context: PipelineContext,
    ) -> None:
        """EnricherAgent should return None for entries without media."""
        agent = EnricherAgent(model="test")
        result = await agent.enrich(entry_without_media, pipeline_context)

        assert result is None

    @pytest.mark.asyncio
    async def test_enricher_skips_existing_content_if_configured(
        self,
        entry_with_existing_content: Entry,
        pipeline_context: PipelineContext,
    ) -> None:
        """EnricherAgent should return None when skip_existing=True and content exists."""
        agent = EnricherAgent(model="test", skip_existing=True)
        result = await agent.enrich(entry_with_existing_content, pipeline_context)

        assert result is None


class TestEnricherAgentMediaTypeSupport:
    """Test EnricherAgent support for different media types."""

    @pytest.mark.asyncio
    async def test_enricher_handles_image_media(
        self,
        pipeline_context: PipelineContext,
    ) -> None:
        """EnricherAgent should handle image media types."""
        entry = Entry(
            id="image-entry",
            title="Image test",
            content="",
            updated=datetime.now(UTC),
            links=[
                Link(
                    rel="enclosure",
                    href="http://example.com/photo.jpg",
                    type="image/jpeg",
                )
            ],
        )

        agent = EnricherAgent(model="test")
        result = await agent.enrich(entry, pipeline_context)
        assert isinstance(result, EnrichmentResult)

    @pytest.mark.asyncio
    async def test_enricher_handles_audio_media(
        self,
        pipeline_context: PipelineContext,
    ) -> None:
        """EnricherAgent should handle audio media types."""
        entry = Entry(
            id="audio-entry",
            title="Audio test",
            content="",
            updated=datetime.now(UTC),
            links=[
                Link(
                    rel="enclosure",
                    href="http://example.com/recording.mp3",
                    type="audio/mpeg",
                )
            ],
        )

        agent = EnricherAgent(model="test")
        result = await agent.enrich(entry, pipeline_context)
        assert isinstance(result, EnrichmentResult)

    @pytest.mark.asyncio
    async def test_enricher_handles_video_media(
        self,
        pipeline_context: PipelineContext,
    ) -> None:
        """EnricherAgent should handle video media types."""
        entry = Entry(
            id="video-entry",
            title="Video test",
            content="",
            updated=datetime.now(UTC),
            links=[
                Link(
                    rel="enclosure",
                    href="http://example.com/clip.mp4",
                    type="video/mp4",
                )
            ],
        )

        agent = EnricherAgent(model="test")
        result = await agent.enrich(entry, pipeline_context)
        assert isinstance(result, EnrichmentResult)


class TestEnricherAgentConfiguration:
    """Test EnricherAgent configuration options."""

    @pytest.mark.asyncio
    async def test_enricher_skip_existing_content(
        self,
        pipeline_context: PipelineContext,
    ) -> None:
        """EnricherAgent should skip entries with existing content when configured."""
        entry = Entry(
            id="entry-with-content",
            title="Entry with content",
            content="Existing content",
            updated=datetime.now(UTC),
            links=[
                Link(
                    rel="enclosure",
                    href="http://example.com/photo.jpg",
                    type="image/jpeg",
                )
            ],
        )

        agent = EnricherAgent(model="test", skip_existing=True)
        result = await agent.enrich(entry, pipeline_context)

        # No enrichment should be generated
        assert result is None


class TestEnricherAgentInterface:
    """Test the public interface of the EnricherAgent."""

    @pytest.mark.asyncio
    async def test_enrich_returns_enrichment_result(
        self, entry_with_image: Entry, pipeline_context: PipelineContext
    ) -> None:
        """Enrich should return an EnrichmentResult object, not an Entry."""
        agent = EnricherAgent(model="test")
        result = await agent.enrich(entry_with_image, pipeline_context)

        assert isinstance(result, EnrichmentResult)
        assert result.description
        assert "A beautiful sunset" in result.description
        assert result.confidence > 0
