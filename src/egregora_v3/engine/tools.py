"""Tools for Pydantic-AI agents with dependency injection.

Tools accept PipelineContext to access:
- ContentLibrary for reading/writing documents
- Vector store for RAG search
- Pipeline metadata

These functions can be registered as Pydantic-AI tools via the @agent.tool decorator.
When used as tools, the agent will inject the RunContext which provides access to deps.
"""

from typing import Any

from egregora_v3.core.context import PipelineContext
from egregora_v3.core.types import Document, DocumentType


async def get_recent_posts(
    context: PipelineContext,
    limit: int = 5,
) -> list[Document]:
    """Get recent posts from the content library.

    Args:
        context: Pipeline context for dependency injection
        limit: Maximum number of posts to return (default: 5)

    Returns:
        List of recent posts, ordered by updated timestamp (newest first)
    """
    # Access ContentLibrary through context
    library = context.library

    # Query posts repository for recent posts
    all_posts = library.posts.list(doc_type=DocumentType.POST)

    # Sort by updated timestamp (newest first)
    all_posts.sort(key=lambda d: d.updated, reverse=True)

    return all_posts[:limit]


async def search_prior_work(
    context: PipelineContext,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search prior work using vector similarity.

    Args:
        context: Pipeline context for dependency injection
        query: Search query text
        limit: Maximum number of results to return (default: 5)

    Returns:
        List of search results with document metadata and similarity scores

    Note:
        This is a placeholder implementation. Full RAG search would require:
        - Vector embeddings of documents
        - Configured vector store (LanceDB)
        - Embedding model for query vectorization
    """
    # Placeholder: In a real implementation, this would:
    # 1. Generate embedding for query using embedding model
    # 2. Search vector store for similar documents
    # 3. Return results with similarity scores

    # For now, return empty list (vector store integration pending)
    return []


async def get_document_by_id(
    context: PipelineContext,
    doc_id: str,
) -> Document | None:
    """Get a document by its ID.

    Args:
        context: Pipeline context for dependency injection
        doc_id: Document ID to retrieve

    Returns:
        Document if found, None otherwise
    """
    library = context.library

    # Try to find in posts first (most common)
    doc = library.posts.get(doc_id)
    if doc:
        return doc

    # Try other repositories
    for repo in [library.journal, library.media, library.profiles, library.enrichments]:
        doc = repo.get(doc_id)
        if doc:
            return doc

    return None


async def count_documents_by_type(
    context: PipelineContext,
    doc_type: DocumentType,
) -> int:
    """Count documents of a specific type.

    Args:
        context: Pipeline context for dependency injection
        doc_type: Document type to count

    Returns:
        Number of documents of the specified type
    """
    library = context.library

    # Get all documents from relevant repository
    # Map document types to repositories
    repo_map = {
        DocumentType.POST: library.posts,
        DocumentType.MEDIA: library.media,
    }

    repo = repo_map.get(doc_type)
    if not repo:
        return 0

    # Count documents of this type
    all_docs = repo.list(doc_type=doc_type)
    return len(all_docs)


async def get_pipeline_metadata(
    context: PipelineContext,
) -> dict[str, Any]:
    """Get current pipeline metadata.

    Args:
        context: Pipeline context for dependency injection

    Returns:
        Dictionary with pipeline metadata including run_id
    """
    # Return metadata with run_id
    return {
        "run_id": context.run_id,
        **context.metadata,
    }


# Tool registry for easy discovery
TOOLS = [
    get_recent_posts,
    search_prior_work,
    get_document_by_id,
    count_documents_by_type,
    get_pipeline_metadata,
]
