import pytest

from egregora.data_primitives.document import Document, DocumentType, UrlContext
from egregora.output_sinks.conventions import StandardUrlConvention


@pytest.fixture
def convention():
    return StandardUrlConvention()


@pytest.fixture
def url_context():
    return UrlContext(base_url="", site_prefix="")


def test_format_media_url_with_suggested_path(convention, url_context):
    """
    Verify that _format_media_url respects the suggested_path if present,
    correctly handling the media subdirectory.
    """
    doc = Document(
        content=b"",
        type=DocumentType.MEDIA,
        id="test-id",
        metadata={
            "filename": "slug-name.jpg",
            "media_type": "image",
        },
        suggested_path="media/images/slug-name.jpg",
    )

    # The canonical URL should be 'media/images/slug-name.jpg'
    url = convention.canonical_url(doc, url_context)

    # ASSERTION (Desired behavior)
    assert url == "/media/images/slug-name.jpg"


def test_format_media_url_infers_subdirectory_from_extension(convention, url_context):
    """
    Verify that if suggested_path is missing, the convention can still
    infer the correct subdirectory from the filename extension.
    """
    doc = Document(
        content=b"",
        type=DocumentType.MEDIA,
        id="test-id",
        metadata={
            "filename": "some-image.png",
            "media_type": "image",
        },
    )

    url = convention.canonical_url(doc, url_context)

    # ASSERTION: When no suggested_path, falls back to posts/media prefix
    # (Current convention uses posts/media/{subfolder}/{filename})
    assert url == "/posts/media/images/some-image.png"
