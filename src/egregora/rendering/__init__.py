"""Output rendering for different site generators."""

from egregora.rendering.base import OutputAdapter, create_output_format, output_registry
from egregora.rendering.hugo import HugoOutputAdapter

# Registry uses old mkdocs.py (two-phase init pattern: __init__() + initialize())
# Writer agent uses new mkdocs_output_format.py directly (constructor injection pattern)
from egregora.rendering.mkdocs import MkDocsOutputAdapter

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
