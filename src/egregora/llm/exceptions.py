"""Custom exceptions for LLM providers."""


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""


class RotatingFallbackError(LLMProviderError):
    """Base exception for errors in the rotating fallback model."""


class AllModelsExhaustedError(RotatingFallbackError):
    """Raised when all models in the fallback rotation are exhausted."""

    def __init__(self, message: str, causes: list[Exception] | None = None) -> None:
        """Initialize with a list of underlying causes."""
        self.causes = causes or []
        super().__init__(message)

    def __str__(self) -> str:
        """Append causes to the string representation."""
        base_msg = super().__str__()
        if not self.causes:
            return base_msg
        causes_str = ", ".join(f"{type(e).__name__}: {e}" for e in self.causes)
        return f"{base_msg}\nUnderlying causes: [{causes_str}]"


class InvalidConfigurationError(RotatingFallbackError):
    """Raised when the rotating fallback model is misconfigured."""
