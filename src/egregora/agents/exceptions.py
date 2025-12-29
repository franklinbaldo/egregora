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

    def __init__(self, window_label: str, reason: str) -> None:
        self.window_label = window_label
        self.reason = reason
        super().__init__(f"Writer agent failed for window '{window_label}': {reason}")


class BannerError(AgentLogicError):
    """Base exception for banner generation errors."""


class BannerTaskPayloadError(BannerError):
    """Raised when a banner task payload is missing, invalid, or cannot be parsed."""

    def __init__(self, task_id: str, reason: str) -> None:
        self.task_id = task_id
        self.reason = reason
        super().__init__(f"Invalid payload for banner task '{task_id}': {reason}")


class BannerTaskDataError(BannerError):
    """Raised when a banner task payload is missing required data."""

    def __init__(self, task_id: str, missing_fields: list[str]) -> None:
        self.task_id = task_id
        self.missing_fields = missing_fields
        super().__init__(f"Banner task '{task_id}' is missing required data: {', '.join(missing_fields)}")
