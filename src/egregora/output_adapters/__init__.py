"""Output rendering for different site generators."""

from egregora.output_adapters.base import OutputAdapter, create_output_format, output_registry

# MkDocsAdapter: Unified MkDocs adapter
from egregora.output_adapters.mkdocs import MkDocsAdapter

# Register output formats on module import
output_registry.register(MkDocsAdapter)

__all__ = [
    "MkDocsAdapter",
    "OutputAdapter",
    "create_output_format",
    "output_registry",
]
