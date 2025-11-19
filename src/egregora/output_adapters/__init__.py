"""Output rendering for different site generators."""

from egregora.output_adapters.base import OutputAdapter, create_output_format, output_registry
from egregora.output_adapters.eleventy_arrow import (
    EleventyArrowAdapter,
    EleventyArrowOutputAdapter,
)

# MkDocsAdapter: Unified MkDocs adapter
from egregora.output_adapters.mkdocs import MkDocsAdapter

# Register output formats on module import
output_registry.register(MkDocsAdapter)
output_registry.register(EleventyArrowOutputAdapter)

__all__ = [
    "EleventyArrowAdapter",
    "EleventyArrowOutputAdapter",
    "MkDocsAdapter",
    "OutputAdapter",
    "create_output_format",
    "output_registry",
]
