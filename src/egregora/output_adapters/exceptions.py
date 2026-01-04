"""Custom exceptions for output adapters."""

from egregora.exceptions import EgregoraError


class OutputAdapterError(EgregoraError):
    """Base class for output adapter errors."""


class DocumentNotFoundError(OutputAdapterError):
    """Raised when a document cannot be found."""

    def __init__(self, doc_type: str, identifier: str) -> None:
        self.doc_type = doc_type
        self.identifier = identifier
        super().__init__(f"Document of type '{doc_type}' with identifier '{identifier}' not found.")


class DocumentIterationError(OutputAdapterError):
    """Raised when a document cannot be read during iteration."""

    def __init__(self, doc_type: str, identifier: str) -> None:
        self.doc_type = doc_type
        self.identifier = identifier
        super().__init__(
            f"Failed to read document of type '{doc_type}' with identifier '{identifier}' during iteration."
        )


class DocumentParsingError(OutputAdapterError):
    """Raised when a document cannot be parsed."""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Failed to parse document at '{path}': {reason}")


class ConfigLoadError(OutputAdapterError):
    """Raised when a site configuration file cannot be loaded or parsed."""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Failed to load or parse config at '{path}': {reason}")


class MarkdownExtensionsError(ConfigLoadError):
    """Raised when markdown extensions cannot be determined due to a config error."""

    def __init__(self, path: str, reason: str) -> None:
        """Initialize the exception."""
        super().__init__(path, f"Failed to load configuration to determine markdown extensions: {reason}")


class UnsupportedDocumentTypeError(OutputAdapterError):
    """Raised when an operation is attempted on an unsupported document type."""

    def __init__(self, doc_type: str) -> None:
        self.doc_type = doc_type
        super().__init__(f"Unsupported document type: '{doc_type}'")


class AdapterNotInitializedError(OutputAdapterError):
    """Raised when an adapter method is called before the adapter is initialized."""

    def __init__(self, message: str = "Adapter has not been initialized. Call initialize() first.") -> None:
        super().__init__(message)


class FilenameGenerationError(OutputAdapterError):
    """Raised when a unique filename cannot be generated."""

    def __init__(self, pattern: str, max_attempts: int) -> None:
        self.pattern = pattern
        self.max_attempts = max_attempts
        super().__init__(f"Could not generate unique filename for '{pattern}' after {max_attempts} attempts.")


class FrontmatterParsingError(OutputAdapterError):
    """Raised when YAML frontmatter is invalid."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Invalid YAML frontmatter: {reason}")


class ProfileNotFoundError(OutputAdapterError):
    """Raised when an author profile cannot be found."""

    def __init__(self, author_uuid: str) -> None:
        self.author_uuid = author_uuid
        super().__init__(f"Profile for author '{author_uuid}' not found.")


class ProfileGenerationError(OutputAdapterError):
    """Raised when a profile document cannot be generated due to missing data."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class IncompleteProfileError(ProfileGenerationError):
    """Raised when a profile is missing essential data like a name."""

    def __init__(self, author_uuid: str, reason: str) -> None:
        self.author_uuid = author_uuid
        self.reason = reason
        super().__init__(f"Profile for author '{author_uuid}' is incomplete: {reason}")


class ProfileMetadataError(ProfileGenerationError):
    """Raised when a document of type PROFILE is missing required metadata."""

    def __init__(self, document_id: str, missing_field: str) -> None:
        self.document_id = document_id
        self.missing_field = missing_field
        super().__init__(
            f"PROFILE document '{document_id}' missing required metadata field: '{missing_field}'"
        )


class CollisionResolutionError(OutputAdapterError):
    """Raised when a filename collision cannot be resolved."""

    def __init__(self, path: str, max_attempts: int) -> None:
        self.path = path
        self.max_attempts = max_attempts
        super().__init__(f"Failed to resolve collision for '{path}' after {max_attempts} attempts.")


class RegistryNotProvidedError(OutputAdapterError):
    """Raised when an OutputSinkRegistry is required but not provided."""

    def __init__(self, message: str = "An OutputSinkRegistry instance must be provided.") -> None:
        super().__init__(message)


class AdapterNotDetectedError(OutputAdapterError):
    """Raised when no suitable output adapter could be detected for a site."""

    def __init__(self, site_root: str) -> None:
        self.site_root = site_root
        super().__init__(f"Could not detect a suitable output adapter for site at '{site_root}'.")


class IndexGenerationError(OutputAdapterError):
    """Raised when a regenerated index page (main, profiles, media) fails."""

    def __init__(self, index_name: str, reason: str) -> None:
        self.index_name = index_name
        self.reason = reason
        super().__init__(f"Failed to generate '{index_name}' index page: {reason}")


class TagsPageGenerationError(OutputAdapterError):
    """Raised when the tags page fails to regenerate."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Failed to regenerate tags page: {reason}")


class ScaffoldingError(OutputAdapterError):
    """Base class for errors during site scaffolding."""


class TemplateRenderingError(ScaffoldingError):
    """Raised when a Jinja2 template fails to render."""

    def __init__(self, template_name: str, reason: str) -> None:
        self.template_name = template_name
        self.reason = reason
        super().__init__(f"Failed to render template '{template_name}': {reason}")


class FileSystemScaffoldError(ScaffoldingError):
    """Raised when a file system operation fails during scaffolding."""

    def __init__(self, path: str, operation: str, reason: str) -> None:
        self.path = path
        self.operation = operation
        self.reason = reason
        super().__init__(f"File system operation '{operation}' failed at '{path}': {reason}")


class PathResolutionError(ScaffoldingError):
    """Raised when site paths cannot be resolved."""

    def __init__(self, site_root: str, reason: str) -> None:
        self.site_root = site_root
        self.reason = reason
        super().__init__(f"Failed to resolve paths for site at '{site_root}': {reason}")


class SiteNotSupportedError(ScaffoldingError):
    """Raised when site discovery fails because the directory is not a supported site type."""

    def __init__(self, site_root: str, reason: str | None = None) -> None:
        self.site_root = site_root
        self.reason = reason
        message = f"Directory '{site_root}' is not a supported site"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class ScaffoldConfigLoadError(ConfigLoadError, ScaffoldingError):
    """Raised when config loading fails during a scaffolding operation."""


# Filesystem operation errors (moved from utils.filesystem)
# ##############################################################################


class FilesystemError(OutputAdapterError):
    """Base exception for filesystem-related errors."""


class MissingMetadataError(FilesystemError):
    """Raised when required metadata for a post is missing."""

    def __init__(self, missing_keys: list[str]) -> None:
        self.missing_keys = missing_keys
        message = f"Missing required metadata keys: {', '.join(missing_keys)}"
        super().__init__(message)


class UniqueFilenameError(FilesystemError):
    """Raised when a unique filename cannot be generated after a set number of attempts."""

    def __init__(self, base_slug: str, attempts: int) -> None:
        self.base_slug = base_slug
        self.attempts = attempts
        message = f"Could not generate a unique filename for slug '{base_slug}' after {attempts} attempts."
        super().__init__(message)


class FilesystemOperationError(FilesystemError):
    """Base exception for file I/O errors."""

    def __init__(self, path: str, original_exception: Exception, message: str | None = None) -> None:
        self.path = path
        self.original_exception = original_exception
        if message is None:
            message = f"An error occurred at path: {self.path}. Original error: {original_exception}"
        super().__init__(message)


class DirectoryCreationError(FilesystemOperationError):
    """Raised when creating a directory fails."""

    def __init__(self, path: str, original_exception: Exception) -> None:
        message = f"Failed to create directory at: {path}. Original error: {original_exception}"
        super().__init__(path, original_exception, message=message)


class FileWriteError(FilesystemOperationError):
    """Raised when writing a file fails."""

    def __init__(self, path: str, original_exception: Exception) -> None:
        message = f"Failed to write file to: {path}. Original error: {original_exception}"
        super().__init__(path, original_exception, message=message)
