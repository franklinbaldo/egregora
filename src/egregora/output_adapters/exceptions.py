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
