from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from egregora.agents.writer import PostMetadata, ReadProfileResult, WritePostResult
from egregora.data_primitives.document import Document, DocumentType

if TYPE_CHECKING:
    from pydantic_ai import RunContext

    from egregora.agents.writer import WriterDeps

logger = logging.getLogger(__name__)


def write_post_tool(ctx: RunContext[WriterDeps], metadata: PostMetadata, content: str) -> WritePostResult:
    doc = Document(
        content=content,
        type=DocumentType.POST,
        metadata=metadata.model_dump(exclude_none=True),
        source_window=ctx.deps.window_label,
    )

    ctx.deps.resources.output.persist(doc)
    logger.info("Writer agent saved post (doc_id: %s)", doc.document_id)
    return WritePostResult(status="success", path=doc.document_id)


def read_profile_tool(ctx: RunContext[WriterDeps], author_uuid: str) -> ReadProfileResult:
    doc = ctx.deps.resources.output.read_document(DocumentType.PROFILE, author_uuid)
    content = doc.content if doc else "No profile exists yet."
    return ReadProfileResult(content=content)


def write_profile_tool(ctx: RunContext[WriterDeps], author_uuid: str, content: str) -> WriteProfileResult:
    doc = Document(
        content=content,
        type=DocumentType.PROFILE,
        metadata={"uuid": author_uuid},
        source_window=ctx.deps.window_label,
    )
    ctx.deps.resources.output.persist(doc)
    logger.info("Writer agent saved profile (doc_id: %s)", doc.document_id)
    return WriteProfileResult(status="success", path=doc.document_id)
