"""Output rendering for different site generators."""

from egregora.output_adapters.base import OutputAdapter, create_output_format, output_registry
from egregora.output_adapters.eleventy_arrow_adapter import EleventyArrowOutputAdapter
from egregora.output_adapters.hugo import HugoOutputAdapter

# MkDocsAdapter: Unified MkDocs adapter
from egregora.output_adapters.mkdocs import MkDocsAdapter

# Register output formats on module import
output_registry.register(MkDocsAdapter)
output_registry.register(HugoOutputAdapter)
output_registry.register(EleventyArrowOutputAdapter)

__all__ = [
    "EleventyArrowOutputAdapter",
    "HugoOutputAdapter",
    "MkDocsAdapter",
    "OutputAdapter",
    "create_output_format",
    "output_registry",
]
