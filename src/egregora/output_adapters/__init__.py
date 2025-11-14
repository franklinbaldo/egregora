"""Output rendering for different site generators."""

from egregora.output_adapters.base import OutputAdapter, create_output_format, output_registry
from egregora.output_adapters.hugo import HugoOutputAdapter

# MkDocsOutputAdapter: Legacy registry-compatible implementation (two-phase init)
# Used by output_registry and create_output_format() factory
# Modern document-centric implementation lives in output_adapters.mkdocs.adapter
# Storage helpers are also consolidated under output_adapters.mkdocs
from egregora.output_adapters.mkdocs import MkDocsOutputAdapter

# Register output formats on module import
output_registry.register(MkDocsOutputAdapter)
output_registry.register(HugoOutputAdapter)

__all__ = [
    "HugoOutputAdapter",
    "MkDocsOutputAdapter",
    "OutputAdapter",
    "create_output_format",
    "output_registry",
]
