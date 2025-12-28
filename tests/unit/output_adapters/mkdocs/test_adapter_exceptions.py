"""Tests for structured exception handling in the MkDocsAdapter."""

from pathlib import Path

import frontmatter
import pytest

from egregora.data_primitives.document import DocumentType
from egregora.output_adapters.exceptions import (
    AdapterNotInitializedError,
    ConfigLoadError,
    DocumentNotFoundError,
    DocumentParsingError,
    FrontmatterParsingError,
    UnsupportedDocumentTypeError,
)
from egregora.output_adapters.mkdocs.adapter import MkDocsAdapter


@pytest.fixture
def adapter(tmp_path: Path) -> MkDocsAdapter:
    """Provides an initialized MkDocsAdapter instance."""
    adapter = MkDocsAdapter()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "posts").mkdir()
    (tmp_path / "mkdocs.yml").write_text("site_name: Test Site")
    adapter.initialize(tmp_path)
    return adapter


def test_get_raises_document_not_found_error(adapter: MkDocsAdapter):
    """Verify get() raises DocumentNotFoundError for a non-existent document."""
    with pytest.raises(DocumentNotFoundError) as excinfo:
        adapter.get(DocumentType.POST, "non-existent-slug")
    assert excinfo.value.doc_type == DocumentType.POST.value
    assert excinfo.value.identifier == "non-existent-slug"


def test_get_raises_document_parsing_error(adapter: MkDocsAdapter):
    """Verify get() raises DocumentParsingError for a file with invalid frontmatter."""
    malformed_post = adapter.posts_dir / "2024-01-01-malformed.md"
    malformed_post.write_text("---\ntitle: Bad YAML\ndate: 2024-01-01\nauthors: [one, two:\n---\n\nContent.")

    with pytest.raises(DocumentParsingError) as excinfo:
        adapter.get(DocumentType.POST, "malformed")
    assert str(malformed_post) in excinfo.value.path
    assert "parsing a flow node" in excinfo.value.reason


def test_get_raises_unsupported_document_type_error_for_invalid_type(adapter: MkDocsAdapter):
    """Verify get() raises UnsupportedDocumentTypeError for an invalid doc_type."""
    unsupported_type = "INVALID_DOC_TYPE"
    with pytest.raises(UnsupportedDocumentTypeError) as excinfo:
        # We are intentionally passing a string where an Enum is expected to test robustness
        adapter.get(unsupported_type, "some-identifier")
    assert excinfo.value.doc_type == unsupported_type


def test_load_config_raises_config_load_error_on_bad_yaml(tmp_path: Path):
    """Verify load_config() raises ConfigLoadError on YAMLError."""
    adapter = MkDocsAdapter()
    bad_config = tmp_path / "mkdocs.yml"
    bad_config.write_text("site_name: Test\ninvalid_yaml: [one, two:")

    with pytest.raises(ConfigLoadError) as excinfo:
        adapter.load_config(tmp_path)
    assert str(bad_config) in excinfo.value.path
    assert "parsing a flow node" in excinfo.value.reason


def test_resolve_document_path_raises_adapter_not_initialized_error():
    """Verify a public method raises AdapterNotInitializedError if not initialized."""
    adapter = MkDocsAdapter()  # Not initialized
    with pytest.raises(AdapterNotInitializedError):
        adapter.resolve_document_path("some/path.md")


def test_parse_frontmatter_raises_on_os_error(adapter: MkDocsAdapter, monkeypatch):
    """Verify _parse_frontmatter raises DocumentParsingError on OSError."""
    # This test targets the private method _parse_frontmatter.
    # The original implementation swallowed OSError and returned {}.
    # The refactored version should raise a specific exception.
    mock_path = Path("/mock/path.md")

    def mock_load_raises_os_error(*args, **kwargs):
        raise OSError("Disk read error")

    monkeypatch.setattr(frontmatter, "load", mock_load_raises_os_error)

    with pytest.raises(DocumentParsingError) as excinfo:
        adapter._parse_frontmatter(mock_path)

    assert "Disk read error" in str(excinfo.value)
    assert str(mock_path) in str(excinfo.value)
