"""Output rendering for different site generators."""

from egregora.rendering.base import OutputFormat, output_registry
from egregora.rendering.hugo import HugoOutputFormat
from egregora.rendering.mkdocs import MkDocsOutputFormat

# Register output formats on module import
output_registry.register(MkDocsOutputFormat)
output_registry.register(HugoOutputFormat)

__all__ = ["HugoOutputFormat", "MkDocsOutputFormat", "OutputFormat", "output_registry"]
