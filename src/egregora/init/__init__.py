"""Initialization stage - Site scaffolding.

This package handles the creation of the MkDocs site structure.
"""

from .scaffolding import ensure_mkdocs_project

__all__ = [
    "ensure_mkdocs_project",
]
