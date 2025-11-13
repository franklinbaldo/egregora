"""Output rendering for different site generators."""

from egregora.output_adapters.base import OutputAdapter, create_output_format, output_registry
from egregora.output_adapters.hugo import HugoOutputAdapter

# MkDocsOutputAdapter: Legacy registry-compatible implementation (two-phase init)
# Used by output_registry and create_output_format() factory
# Modern Document-based implementation in mkdocs_output_adapter.py (used directly by writer)
# Storage implementations shared via mkdocs_storage.py (used by both MkDocs and Hugo)
from egregora.output_adapters.mkdocs import MkDocsOutputAdapter
from egregora.output_adapters.eleventy_arrow_adapter import EleventyArrowOutputAdapter

# Register output formats on module import
output_registry.register(MkDocsOutputAdapter)
output_registry.register(HugoOutputAdapter)
output_registry.register(EleventyArrowOutputAdapter)

__all__ = [
    "EleventyArrowOutputAdapter",
    "HugoOutputAdapter",
    "MkDocsOutputAdapter",
    "OutputAdapter",
    "create_output_format",
    "output_registry",
]
