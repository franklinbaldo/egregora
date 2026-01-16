"""Journal-based execution log utilities."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from egregora.data_primitives.document import Document, DocumentType

if TYPE_CHECKING:
    from datetime import datetime

    from egregora.data_primitives.protocols import OutputSink

logger = logging.getLogger(__name__)


def window_already_processed(output_sink: OutputSink, signature: str) -> bool:
    """Check if a window with the given signature has already been processed.

    Iterates through existing JOURNAL documents in the sink to find a match.
    Reliability depends on the sink's list() implementation.

    Args:
        output_sink: The output sink to query.
        signature: The window signature to look for.

    Returns:
        True if a JOURNAL with the matching signature exists, False otherwise.

    """
    try:
        # Optimization: Some sinks might support filtering by metadata in the future,
        # but for now we iterate the lightweight metadata list.
        # Ideally, we would ask the sink for just JOURNAL types.
        for journal_meta in output_sink.list(DocumentType.JOURNAL):
            if journal_meta.metadata.get("window_signature") == signature:
                logger.debug("Found existing JOURNAL for signature: %s", signature[:12])
                return True
        return False
    except Exception as e:
        logger.warning("Error checking for existing JOURNAL: %s. Assuming not processed.", e)
        return False


def create_journal_document(
    signature: str,
    run_id: UUID | None,
    window_start: datetime,
    window_end: datetime,
    model: str,
    posts_generated: int = 0,
    profiles_updated: int = 0,
    reasoning: str = "",
) -> Document:
    """Create a JOURNAL document for a processed window.

    Args:
        signature: The unique window signature (hash).
        run_id: The ID of the pipeline run.
        window_start: Start timestamp of the window.
        window_end: End timestamp of the window.
        model: The model used for processing.
        posts_generated: Count of posts generated.
        profiles_updated: Count of profiles updated.
        reasoning: Optional text describing the reasoning or summary.

    Returns:
        A Document object of type JOURNAL.

    """
    content = reasoning or f"Window processed: {window_start.isoformat()} to {window_end.isoformat()}"

    metadata = {
        "window_signature": signature,
        "run_id": str(run_id) if run_id else None,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "model": model,
        "posts_generated": posts_generated,
        "profiles_updated": profiles_updated,
    }

    return Document(
        type=DocumentType.JOURNAL,
        content=content,
        metadata=metadata,
        id=f"journal-{signature[:12]}",  # Semantic ID based on signature
    )
