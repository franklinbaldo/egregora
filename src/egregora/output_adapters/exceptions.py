"""Custom exceptions for output adapters."""


class OutputAdapterError(Exception):
    """Base class for output adapter errors."""


class DocumentNotFoundError(OutputAdapterError):
    """Raised when a document cannot be found."""

    def __init__(self, doc_type: str, identifier: str) -> None:
        self.doc_type = doc_type
        self.identifier = identifier
        super().__init__(f"Document of type '{doc_type}' with identifier '{identifier}' not found.")


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
