"""Custom exceptions for agent-related errors."""


class AgentLogicError(Exception):
    """Base exception for agent-related logical errors."""


class JournalTemplateError(AgentLogicError):
    """Raised when a journal template cannot be found or rendered."""

    def __init__(self, template_name: str, reason: str) -> None:
        self.template_name = template_name
        self.reason = reason
        super().__init__(f"Failed to process journal template '{template_name}': {reason}")


class JournalFileSystemError(AgentLogicError):
    """Raised when a journal file cannot be written to the filesystem."""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Filesystem error for journal at '{path}': {reason}")


class WriterAgentExecutionError(AgentLogicError):
    """Raised when the writer agent fails during execution."""

    def __init__(self, window_label: str) -> None:
        self.window_label = window_label
        super().__init__(f"Writer agent failed for window '{window_label}'")
