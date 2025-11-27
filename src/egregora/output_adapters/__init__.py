"""Output rendering for different site generators."""

from egregora.output_adapters.base import create_output_format, output_registry
from egregora.output_adapters.mkdocs import MkDocsAdapter
from egregora.output_adapters.parquet.adapter import ParquetAdapter

# Register output formats on module import
output_registry.register(MkDocsAdapter)
output_registry.register(ParquetAdapter)

__all__ = [
    "MkDocsAdapter",
    "ParquetAdapter",
    "create_output_format",
    "output_registry",
]
