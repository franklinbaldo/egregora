"""Output rendering for different site generators."""

from egregora.output_adapters.base import (
    BaseOutputSink,
    OutputSinkRegistry,
    create_output_registry,
    create_output_sink,
)
from egregora.output_adapters.mkdocs import MkDocsAdapter
# DISABLED: Removing parquet adapter as part of simplification
# from egregora.output_adapters.parquet.adapter import ParquetAdapter


def create_default_output_registry() -> OutputSinkRegistry:
    """Create a registry pre-populated with built-in adapters."""
    registry = create_output_registry()
    registry.register(MkDocsAdapter)
    # DISABLED: Removing parquet adapter
    # registry.register(ParquetAdapter)
    return registry


__all__ = [
    "BaseOutputSink",
    "MkDocsAdapter",
    "OutputSinkRegistry",
    # DISABLED: Removing parquet adapter
    # "ParquetAdapter",
    "create_default_output_registry",
    "create_output_registry",
    "create_output_sink",
]
