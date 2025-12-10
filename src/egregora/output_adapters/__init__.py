"""Output rendering for different site generators."""

from egregora.output_adapters.base import (
    BaseOutputSink,
    OutputSinkRegistry,
    create_output_registry,
    create_output_sink,
)
from egregora.output_adapters.mkdocs import MkDocsAdapter
from egregora.output_adapters.parquet.adapter import ParquetAdapter


def create_default_output_registry() -> OutputSinkRegistry:
    """Create a registry pre-populated with built-in adapters."""
    registry = create_output_registry()
    registry.register(MkDocsAdapter)
    registry.register(ParquetAdapter)
    return registry


__all__ = [
    "BaseOutputSink",
    "MkDocsAdapter",
    "OutputSinkRegistry",
    "ParquetAdapter",
    "create_default_output_registry",
    "create_output_registry",
    "create_output_sink",
]
