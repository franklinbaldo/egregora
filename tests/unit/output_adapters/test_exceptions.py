"""Tests for custom exceptions in output adapters."""

import pytest

from egregora.output_sinks.exceptions import (
    AdapterNotInitializedError,
    CollisionResolutionError,
    ConfigLoadError,
    DocumentNotFoundError,
    DocumentParsingError,
    FilenameGenerationError,
    FrontmatterParsingError,
    ProfileGenerationError,
    ProfileNotFoundError,
    RegistryNotProvidedError,
    UnsupportedDocumentTypeError,
)


@pytest.mark.parametrize(
    ("doc_type", "identifier", "expected_message"),
    [
        ("post", "my-post", "Document of type 'post' with identifier 'my-post' not found."),
        ("page", "about-us", "Document of type 'page' with identifier 'about-us' not found."),
    ],
)
def test_document_not_found_error(doc_type, identifier, expected_message):
    """Test that DocumentNotFoundError formats its message correctly."""
    err = DocumentNotFoundError(doc_type, identifier)
    assert err.doc_type == doc_type
    assert err.identifier == identifier
    assert str(err) == expected_message


@pytest.mark.parametrize(
    ("path", "reason", "expected_message"),
    [
        (
            "/path/to/doc.md",
            "Invalid format",
            "Failed to parse document at '/path/to/doc.md': Invalid format",
        ),
        ("another/doc.txt", "UTF-8 error", "Failed to parse document at 'another/doc.txt': UTF-8 error"),
    ],
)
def test_document_parsing_error(path, reason, expected_message):
    """Test that DocumentParsingError formats its message correctly."""
    err = DocumentParsingError(path, reason)
    assert err.path == path
    assert err.reason == reason
    assert str(err) == expected_message


@pytest.mark.parametrize(
    ("path", "reason", "expected_message"),
    [
        (
            "/path/to/config.yml",
            "YAML error",
            "Failed to load or parse config at '/path/to/config.yml': YAML error",
        ),
        (
            "site.toml",
            "TOML syntax error",
            "Failed to load or parse config at 'site.toml': TOML syntax error",
        ),
    ],
)
def test_config_load_error(path, reason, expected_message):
    """Test that ConfigLoadError formats its message correctly."""
    err = ConfigLoadError(path, reason)
    assert err.path == path
    assert err.reason == reason
    assert str(err) == expected_message


@pytest.mark.parametrize(
    ("doc_type", "expected_message"),
    [
        ("video", "Unsupported document type: 'video'"),
        ("audio", "Unsupported document type: 'audio'"),
    ],
)
def test_unsupported_document_type_error(doc_type, expected_message):
    """Test that UnsupportedDocumentTypeError formats its message correctly."""
    err = UnsupportedDocumentTypeError(doc_type)
    assert err.doc_type == doc_type
    assert str(err) == expected_message


@pytest.mark.parametrize(
    ("message", "expected_message"),
    [
        (None, "Adapter has not been initialized. Call initialize() first."),
        ("Custom error message", "Custom error message"),
    ],
)
def test_adapter_not_initialized_error(message, expected_message):
    """Test that AdapterNotInitializedError has the correct message."""
    err = AdapterNotInitializedError(message) if message else AdapterNotInitializedError()
    assert str(err) == expected_message


@pytest.mark.parametrize(
    ("pattern", "max_attempts", "expected_message"),
    [
        (
            "test-pattern",
            5,
            "Could not generate unique filename for 'test-pattern' after 5 attempts.",
        ),
        ("image-{uuid}", 10, "Could not generate unique filename for 'image-{uuid}' after 10 attempts."),
    ],
)
def test_filename_generation_error(pattern, max_attempts, expected_message):
    """Test that FilenameGenerationError formats its message correctly."""
    err = FilenameGenerationError(pattern, max_attempts)
    assert err.pattern == pattern
    assert err.max_attempts == max_attempts
    assert str(err) == expected_message


@pytest.mark.parametrize(
    ("reason", "expected_message"),
    [
        ("Missing key", "Invalid YAML frontmatter: Missing key"),
        ("Invalid indentation", "Invalid YAML frontmatter: Invalid indentation"),
    ],
)
def test_frontmatter_parsing_error(reason, expected_message):
    """Test that FrontmatterParsingError formats its message correctly."""
    err = FrontmatterParsingError(reason)
    assert err.reason == reason
    assert str(err) == expected_message


@pytest.mark.parametrize(
    ("author_uuid", "expected_message"),
    [
        ("uuid-123", "Profile for author 'uuid-123' not found."),
        ("another-uuid", "Profile for author 'another-uuid' not found."),
    ],
)
def test_profile_not_found_error(author_uuid, expected_message):
    """Test that ProfileNotFoundError formats its message correctly."""
    err = ProfileNotFoundError(author_uuid)
    assert err.author_uuid == author_uuid
    assert str(err) == expected_message


@pytest.mark.parametrize(
    ("message", "expected_message"),
    [
        ("Missing name", "Missing name"),
        ("Invalid email", "Invalid email"),
    ],
)
def test_profile_generation_error(message, expected_message):
    """Test that ProfileGenerationError formats its message correctly."""
    err = ProfileGenerationError(message)
    assert str(err) == expected_message


@pytest.mark.parametrize(
    ("path", "max_attempts", "expected_message"),
    [
        (
            "/path/to/file.md",
            100,
            "Failed to resolve collision for '/path/to/file.md' after 100 attempts.",
        ),
        ("another/path.txt", 50, "Failed to resolve collision for 'another/path.txt' after 50 attempts."),
    ],
)
def test_collision_resolution_error(path, max_attempts, expected_message):
    """Test that CollisionResolutionError formats its message correctly."""
    err = CollisionResolutionError(path, max_attempts)
    assert err.path == path
    assert err.max_attempts == max_attempts
    assert str(err) == expected_message


@pytest.mark.parametrize(
    ("message", "expected_message"),
    [
        (None, "An OutputSinkRegistry instance must be provided."),
        ("A custom error message", "A custom error message"),
    ],
)
def test_registry_not_provided_error(message, expected_message):
    """Test that RegistryNotProvidedError has the correct message."""
    err = RegistryNotProvidedError(message) if message else RegistryNotProvidedError()
    assert str(err) == expected_message
