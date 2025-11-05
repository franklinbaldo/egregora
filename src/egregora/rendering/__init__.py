"""Output rendering for different site generators."""

from egregora.rendering.base import OutputFormat
from egregora.rendering.hugo import HugoOutputFormat
from egregora.rendering.mkdocs import MkDocsOutputFormat

__all__ = ["HugoOutputFormat", "MkDocsOutputFormat", "OutputFormat"]
