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


class AgentExecutionError(AgentLogicError):
    """Raised when the agent's main execution loop fails unexpectedly."""

    def __init__(self, window_label: str, reason: str) -> None:
        self.window_label = window_label
        self.reason = reason
        super().__init__(f"Agent execution failed for window '{window_label}': {reason}")


class JournalDataError(AgentLogicError):
    """Raised when the data provided for journal creation is invalid."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Invalid data for journal: {reason}")


class FormatInstructionError(AgentLogicError):
    """Raised when format instructions cannot be loaded."""

    def __init__(self, format_name: str, reason: str) -> None:
        self.format_name = format_name
        self.reason = reason
        super().__init__(f"Could not load instructions for format '{format_name}': {reason}")
