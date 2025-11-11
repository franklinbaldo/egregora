"""Output rendering for different site generators."""

from egregora.rendering.base import OutputFormat, create_output_format, output_registry
from egregora.rendering.hugo import HugoOutputFormat

# Registry uses old mkdocs.py (two-phase init pattern: __init__() + initialize())
# Writer agent uses new mkdocs_output_format.py directly (constructor injection pattern)
from egregora.rendering.mkdocs import MkDocsOutputFormat

# Register output formats on module import
output_registry.register(MkDocsOutputFormat)
output_registry.register(HugoOutputFormat)

__all__ = [
    "HugoOutputFormat",
    "MkDocsOutputFormat",
    "OutputFormat",
    "create_output_format",
    "output_registry",
]
