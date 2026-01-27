from unittest.mock import patch

from egregora.data_primitives.document import Document, DocumentType
from egregora.output_sinks.mkdocs.adapter import MkDocsAdapter


def test_clean_metadata_removes_none_values():
    metadata = {"title": None, "slug": "test-slug", "description": "valid", "missing": None}
    cleaned = MkDocsAdapter._clean_metadata(metadata)
    assert "title" not in cleaned
    assert "missing" not in cleaned
    assert cleaned["slug"] == "test-slug"
    assert cleaned["description"] == "valid"


@patch("egregora.output_sinks.mkdocs.adapter.yaml.dump")
def test_write_enrichment_doc_sanitizes_metadata(mock_yaml_dump, tmp_path):
    adapter = MkDocsAdapter()
    adapter.media_dir = tmp_path / "media"
    adapter.media_dir.mkdir(parents=True)

    doc = Document(
        content="Test content",
        type=DocumentType.ENRICHMENT_IMAGE,
        metadata={"title": None, "slug": "test-image", "categories": ["Enrichment"]},
    )

    path = adapter.media_dir / "test.md"
    adapter._write_enrichment_doc(doc, path)

    # Verify yaml.dump was called with sanitized metadata
    args, _ = mock_yaml_dump.call_args
    dumped_metadata = args[0]

    assert "title" not in dumped_metadata
    assert dumped_metadata["slug"] == "test-image"
    assert "Enrichment" in dumped_metadata["categories"]


@patch("egregora.output_sinks.mkdocs.adapter.yaml.dump")
def test_write_profile_doc_sanitizes_metadata(mock_yaml_dump, tmp_path):
    adapter = MkDocsAdapter()
    adapter.profiles_dir = tmp_path / "profiles"
    adapter.profiles_dir.mkdir(parents=True)
    adapter._site_root = tmp_path

    # Mock documents() to return empty list for related posts
    with patch.object(adapter, "documents", return_value=[]):
        doc = Document(
            content="Profile content",
            type=DocumentType.PROFILE,
            metadata={"uuid": "user123", "title": None, "name": "User Name"},
        )

        path = adapter.profiles_dir / "user123.md"
        adapter._write_profile_doc(doc, path)

        # Verify yaml.dump was called with sanitized metadata
        args, _ = mock_yaml_dump.call_args
        dumped_metadata = args[0]

        assert "title" not in dumped_metadata
        assert dumped_metadata["uuid"] == "user123"
