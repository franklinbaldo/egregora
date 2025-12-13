"""Output rendering for different site generators."""

from egregora.output_adapters.base import (
    BaseOutputSink,
    OutputSinkRegistry,
    create_output_registry,
    create_output_sink,
)
from egregora.output_adapters.mkdocs import MkDocsAdapter


def create_default_output_registry() -> OutputSinkRegistry:
    """Create a registry pre-populated with built-in adapters."""
    registry = create_output_registry()
    registry.register(MkDocsAdapter)
    return registry


__all__ = [
    "BaseOutputSink",
    "MkDocsAdapter",
    "OutputSinkRegistry",
    "create_default_output_registry",
    "create_output_registry",
    "create_output_sink",
]
