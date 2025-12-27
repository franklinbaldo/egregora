"""Tests for custom exceptions in output adapters."""

from egregora.output_adapters.exceptions import (
    AdapterNotInitializedError,
    CollisionResolutionError,
    ConfigLoadError,
    DocumentNotFoundError,
    DocumentParsingError,
    FrontmatterParsingError,
    ProfileGenerationError,
    ProfileNotFoundError,
    UnsupportedDocumentTypeError,
)


def test_document_not_found_error():
    """Test that DocumentNotFoundError formats its message correctly."""
    err = DocumentNotFoundError("post", "my-post")
    assert err.doc_type == "post"
    assert err.identifier == "my-post"
    assert str(err) == "Document of type 'post' with identifier 'my-post' not found."


def test_document_parsing_error():
    """Test that DocumentParsingError formats its message correctly."""
    err = DocumentParsingError("/path/to/doc.md", "Invalid format")
    assert err.path == "/path/to/doc.md"
    assert err.reason == "Invalid format"
    assert str(err) == "Failed to parse document at '/path/to/doc.md': Invalid format"


def test_config_load_error():
    """Test that ConfigLoadError formats its message correctly."""
    err = ConfigLoadError("/path/to/config.yml", "YAML error")
    assert err.path == "/path/to/config.yml"
    assert err.reason == "YAML error"
    assert str(err) == "Failed to load or parse config at '/path/to/config.yml': YAML error"


def test_unsupported_document_type_error():
    """Test that UnsupportedDocumentTypeError formats its message correctly."""
    err = UnsupportedDocumentTypeError("video")
    assert err.doc_type == "video"
    assert str(err) == "Unsupported document type: 'video'"


def test_adapter_not_initialized_error():
    """Test that AdapterNotInitializedError has the correct default message."""
    err = AdapterNotInitializedError()
    assert str(err) == "Adapter has not been initialized. Call initialize() first."


def test_frontmatter_parsing_error():
    """Test that FrontmatterParsingError formats its message correctly."""
    err = FrontmatterParsingError("Missing key")
    assert err.reason == "Missing key"
    assert str(err) == "Invalid YAML frontmatter: Missing key"


def test_profile_not_found_error():
    """Test that ProfileNotFoundError formats its message correctly."""
    err = ProfileNotFoundError("uuid-123")
    assert err.author_uuid == "uuid-123"
    assert str(err) == "Profile for author 'uuid-123' not found."


def test_profile_generation_error():
    """Test that ProfileGenerationError formats its message correctly."""
    err = ProfileGenerationError("Missing name")
    assert str(err) == "Missing name"


def test_collision_resolution_error():
    """Test that CollisionResolutionError formats its message correctly."""
    err = CollisionResolutionError("/path/to/file.md", 100)
    assert err.path == "/path/to/file.md"
    assert err.max_attempts == 100
    assert str(err) == "Failed to resolve collision for '/path/to/file.md' after 100 attempts."
