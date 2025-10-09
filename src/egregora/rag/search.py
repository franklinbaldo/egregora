"""DEPRECATED: Legacy TF-IDF search module.

The classic `egregora.rag.search` entrypoint has been superseded by the
unified retrieval pipeline. This module remains as a thin compatibility
layer for older integrations and will be removed in a future release.
"""

from __future__ import annotations

from typing import Any

__all__ = ["search"]


def search(*_: Any, **__: Any) -> None:
    """Placeholder search function that raises a helpful error.

    The historical TF-IDF implementation is no longer bundled with the
    project. Callers should migrate to :mod:`egregora.rag.index` for indexing
    and :mod:`egregora.rag.query_gen` for querying.
    """

    raise RuntimeError(
        "The TF-IDF search module has been removed. Use the new RAG pipeline "
        "under `egregora.rag` instead."
    )
