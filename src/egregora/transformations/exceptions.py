"""Exceptions for the transformations module."""
from egregora.exceptions import EgregoraError


class TransformationsError(EgregoraError):
    """Base exception for transformations errors."""


class InvalidStepUnitError(TransformationsError):
    """Raised when an invalid step_unit is provided."""

    def __init__(self, step_unit: str) -> None:
        self.step_unit = step_unit
        super().__init__(f"Invalid step_unit: {step_unit}")


class InvalidSplitError(TransformationsError):
    """Raised when an invalid number of splits is provided."""

    def __init__(self, n: int) -> None:
        self.n = n
        super().__init__(f"Invalid number of splits: {n}")
