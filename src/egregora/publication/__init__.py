"""Publication stage - Site scaffolding and output generation.

This package handles final output:
- MkDocs site structure creation
- Template rendering for homepage, about, etc.
"""

from . import site
from .site import ensure_mkdocs_project

__all__ = [
    "site",
    "ensure_mkdocs_project",
]
