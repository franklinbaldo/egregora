"""Output rendering for different site generators."""

from egregora.output_adapters.base import OutputAdapterRegistry, create_output_format, create_output_registry
from egregora.output_adapters.mkdocs import MkDocsAdapter
from egregora.output_adapters.parquet.adapter import ParquetAdapter


def create_default_output_registry() -> OutputAdapterRegistry:
    """Create a registry pre-populated with built-in adapters."""
    registry = create_output_registry()
    registry.register(MkDocsAdapter)
    registry.register(ParquetAdapter)
    return registry


__all__ = [
    "MkDocsAdapter",
    "OutputAdapterRegistry",
    "ParquetAdapter",
    "create_default_output_registry",
    "create_output_format",
    "create_output_registry",
]
