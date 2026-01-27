"""Tests for media-specific enrichment types (ENRICHMENT_IMAGE, ENRICHMENT_VIDEO, ENRICHMENT_AUDIO)."""

from pathlib import Path

import pytest

from egregora.data_primitives.document import Document, DocumentType, UrlContext
from egregora.output_sinks.conventions import RouteConfig, StandardUrlConvention
from egregora.output_sinks.mkdocs import MkDocsAdapter


class TestMediaSpecificEnrichmentTypes:
    """Test that media-specific enrichment types route to correct folders."""

    @pytest.fixture
    def convention(self) -> StandardUrlConvention:
        return StandardUrlConvention(RouteConfig())

    @pytest.fixture
    def ctx(self) -> UrlContext:
        return UrlContext(base_url="", site_prefix="")

    def test_enrichment_image_url_goes_to_images_subfolder(
        self, convention: StandardUrlConvention, ctx: UrlContext
    ) -> None:
        """ENRICHMENT_IMAGE documents should generate URLs under media/images/."""
        doc = Document(
            content="A beautiful sunset photo",
            type=DocumentType.ENRICHMENT_IMAGE,
            metadata={"slug": "sunset-photo", "media_type": "image"},
            id="sunset-photo",
        )
        url = convention.canonical_url(doc, ctx)
        assert "/posts/media/images/" in url
        assert "sunset-photo" in url

    def test_enrichment_video_url_goes_to_videos_subfolder(
        self, convention: StandardUrlConvention, ctx: UrlContext
    ) -> None:
        """ENRICHMENT_VIDEO documents should generate URLs under media/videos/."""
        doc = Document(
            content="A tutorial video",
            type=DocumentType.ENRICHMENT_VIDEO,
            metadata={"slug": "tutorial-video", "media_type": "video"},
            id="tutorial-video",
        )
        url = convention.canonical_url(doc, ctx)
        assert "/posts/media/videos/" in url
        assert "tutorial-video" in url

    def test_enrichment_audio_url_goes_to_audio_subfolder(
        self, convention: StandardUrlConvention, ctx: UrlContext
    ) -> None:
        """ENRICHMENT_AUDIO documents should generate URLs under media/audio/."""
        doc = Document(
            content="A podcast episode",
            type=DocumentType.ENRICHMENT_AUDIO,
            metadata={"slug": "podcast-episode", "media_type": "audio"},
            id="podcast-episode",
        )
        url = convention.canonical_url(doc, ctx)
        assert "/posts/media/audio/" in url
        assert "podcast-episode" in url

    def test_enrichment_media_fallback_still_works(
        self, convention: StandardUrlConvention, ctx: UrlContext
    ) -> None:
        """ENRICHMENT_MEDIA (generic) should still work as fallback."""
        doc = Document(
            content="Unknown media type",
            type=DocumentType.ENRICHMENT_MEDIA,
            metadata={"slug": "unknown-media"},
            id="unknown-media",
        )
        url = convention.canonical_url(doc, ctx)
        assert "/posts/media/" in url


class TestMkDocsAdapterMediaSpecificPaths:
    """Test that MkDocsAdapter persists media-specific enrichments to correct folders."""

    @pytest.fixture
    def adapter(self, tmp_path: Path) -> MkDocsAdapter:
        adapter = MkDocsAdapter()
        adapter.initialize(tmp_path)
        return adapter

    def test_enrichment_image_persisted_to_images_folder(self, adapter: MkDocsAdapter) -> None:
        """ENRICHMENT_IMAGE documents are persisted to media/images/."""
        doc = Document(
            content="# Image Description\n\nA sunset photo.",
            type=DocumentType.ENRICHMENT_IMAGE,
            metadata={"slug": "sunset-photo", "media_type": "image"},
            id="sunset-photo",
        )
        adapter.persist(doc)

        # Check the path was stored correctly
        stored_path = adapter._index[doc.document_id]
        assert stored_path.exists()
        assert "images" in stored_path.parts
        assert stored_path.name.startswith("sunset-photo")
        assert stored_path.name.endswith(".md")

    def test_enrichment_video_persisted_to_videos_folder(self, adapter: MkDocsAdapter) -> None:
        """ENRICHMENT_VIDEO documents are persisted to media/videos/."""
        doc = Document(
            content="# Video Description\n\nA tutorial video.",
            type=DocumentType.ENRICHMENT_VIDEO,
            metadata={"slug": "tutorial-video", "media_type": "video"},
            id="tutorial-video",
        )
        adapter.persist(doc)

        stored_path = adapter._index[doc.document_id]
        assert stored_path.exists()
        assert "videos" in stored_path.parts
        assert stored_path.name.startswith("tutorial-video")
        assert stored_path.name.endswith(".md")

    def test_enrichment_audio_persisted_to_audio_folder(self, adapter: MkDocsAdapter) -> None:
        """ENRICHMENT_AUDIO documents are persisted to media/audio/."""
        doc = Document(
            content="# Audio Description\n\nA podcast episode.",
            type=DocumentType.ENRICHMENT_AUDIO,
            metadata={"slug": "podcast-episode", "media_type": "audio"},
            id="podcast-episode",
        )
        adapter.persist(doc)

        stored_path = adapter._index[doc.document_id]
        assert stored_path.exists()
        assert "audio" in stored_path.parts
        assert stored_path.name.startswith("podcast-episode")
        assert stored_path.name.endswith(".md")

    def test_all_media_types_organize_into_separate_folders(self, adapter: MkDocsAdapter) -> None:
        """Multiple media types should each go to their own subfolder."""
        image_doc = Document(
            content="Image", type=DocumentType.ENRICHMENT_IMAGE, metadata={"slug": "img1"}, id="img1"
        )
        video_doc = Document(
            content="Video", type=DocumentType.ENRICHMENT_VIDEO, metadata={"slug": "vid1"}, id="vid1"
        )
        audio_doc = Document(
            content="Audio", type=DocumentType.ENRICHMENT_AUDIO, metadata={"slug": "aud1"}, id="aud1"
        )

        for doc in (image_doc, video_doc, audio_doc):
            adapter.persist(doc)

        image_path = adapter._index["img1"]
        video_path = adapter._index["vid1"]
        audio_path = adapter._index["aud1"]

        # All paths should be distinct subfolders
        assert image_path.parent.name == "images"
        assert video_path.parent.name == "videos"
        assert audio_path.parent.name == "audio"

        # All under the same media directory
        assert image_path.parent.parent == video_path.parent.parent == audio_path.parent.parent
