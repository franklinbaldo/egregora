"""Test that banner path prediction matches actual saved paths."""


from egregora.agents.banner.batch_processor import BannerBatchProcessor, BannerTaskEntry
from egregora.agents.banner.image_generation import ImageGenerationResult
from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import UrlContext
from egregora.output_adapters.conventions import StandardUrlConvention
from egregora.utils.paths import slugify


class _FakeProvider:
    """Fake provider that returns a successful image generation result."""

    def generate(self, request):
        return ImageGenerationResult(
            image_bytes=b"fake-image-data",
            mime_type="image/jpeg",
        )


def test_predicted_path_matches_actual():
    """Test that the predicted banner path matches the actual saved path."""
    post_slug = "test-post-banner"

    # 1. Simulate path prediction (what happens in capabilities.py)
    slug = slugify(post_slug, max_len=60)
    extension = ".jpg"
    filename = f"{slug}{extension}"

    placeholder_doc = Document(
        content="",
        type=DocumentType.MEDIA,
        metadata={"filename": filename},
        id=filename,
    )

    url_convention = StandardUrlConvention()
    url_context = UrlContext(base_url="", site_prefix="")

    predicted_url = url_convention.canonical_url(placeholder_doc, url_context)
    predicted_path = predicted_url.lstrip("/")

    # 2. Simulate actual banner generation (what happens in batch_processor.py)
    processor = BannerBatchProcessor(provider=_FakeProvider())

    task = BannerTaskEntry(
        task_id="test-task-123",
        title="Test Post",
        summary="Test summary",
        slug=post_slug,
        language="pt-BR",
        metadata={},
    )

    results = processor.process_tasks([task])
    assert len(results) == 1
    assert results[0].success

    actual_doc = results[0].document
    assert actual_doc is not None

    actual_url = url_convention.canonical_url(actual_doc, url_context)
    actual_path = actual_url.lstrip("/")

    # 3. Verify paths match
    assert predicted_path == actual_path, f"Path mismatch! Predicted: {predicted_path}, Actual: {actual_path}"
    assert actual_doc.document_id == filename
    assert actual_doc.metadata["filename"] == filename


def test_mime_type_to_extension_mapping():
    """Test that different MIME types map to correct extensions."""
    test_cases = [
        ("image/jpeg", ".jpg"),
        ("image/png", ".png"),
        ("image/webp", ".webp"),
        ("image/gif", ".gif"),
        ("image/svg+xml", ".svg"),
        ("image/unknown", ".jpg"),  # Default fallback
    ]

    for mime_type, expected_ext in test_cases:
        extension = BannerBatchProcessor._get_extension_for_mime_type(mime_type)
        assert extension == expected_ext, f"MIME {mime_type} should map to {expected_ext}, got {extension}"


def test_banner_document_has_required_fields():
    """Test that generated banner documents have all required fields for path prediction."""
    processor = BannerBatchProcessor(provider=_FakeProvider())

    task = BannerTaskEntry(
        task_id="test-456",
        title="Another Test",
        summary="Summary here",
        slug="another-test-post",
        language="en",
        metadata={},
    )

    results = processor.process_tasks([task])
    doc = results[0].document

    # Verify all required fields are present
    assert doc is not None
    assert doc.id is not None, "Document should have explicit ID"
    assert doc.metadata.get("filename") is not None, "Document should have filename in metadata"
    assert doc.metadata.get("mime_type") is not None, "Document should have mime_type"
    assert doc.type == DocumentType.MEDIA

    # Verify filename matches ID
    assert doc.document_id == doc.metadata["filename"]

    # Verify filename has extension
    assert "." in doc.metadata["filename"], "Filename should include extension"
