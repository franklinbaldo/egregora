"""Client-side search index generation."""

import json
import logging
from pathlib import Path

from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.document import DocumentType
from egregora.data_primitives.protocols import OutputSink
from egregora.rag.embeddings_async import embed_texts_async

logger = logging.getLogger(__name__)

SUMMARY_MAX_LENGTH = 150
CONTENT_SNIPPET_LENGTH = 200


async def build_client_search_index(
    adapter: OutputSink,
    config: EgregoraConfig,
    output_path: Path,
) -> None:
    """Generate a lightweight vector index for client-side related posts.

    Args:
        adapter: Output adapter to read posts from.
        config: Configuration for embedding models.
        output_path: Path to write the JSON file (e.g., site_root/assets/data/search.json).

    """
    logger.info("Building client-side search index...")

    # 1. Gather Posts
    # We only care about published posts with summaries
    posts = []
    texts_to_embed = []

    # We iterate documents (lazy) and materialize only POSTs
    for doc in adapter.documents():
        if doc.type != DocumentType.POST:
            continue

        summary = doc.metadata.get("summary", "")
        title = doc.metadata.get("title", "")

        # Fallback: if no summary, use title + start of content
        if not summary:
            content_snippet = (
                doc.content[:CONTENT_SNIPPET_LENGTH] if isinstance(doc.content, str) else ""
            )
            text_to_embed = f"{title}: {content_snippet}"
        else:
            text_to_embed = summary

        # Store metadata needed for the frontend
        # Get canonical URL relative to site root for matching
        url = adapter.url_convention.canonical_url(doc, adapter.url_context)

        posts.append(
            {
                "u": url,
                "t": title,
                "d": doc.metadata.get("date", ""),
                "s": (
                    summary[:SUMMARY_MAX_LENGTH] + "..."
                    if len(summary) > SUMMARY_MAX_LENGTH
                    else summary
                ),  # Truncate visual summary
            }
        )
        texts_to_embed.append(text_to_embed)

    if not posts:
        logger.warning("No posts found to index.")
        return

    # 2. Batch Embeddings
    # We use task_type="RETRIEVAL_DOCUMENT" as these are the targets
    try:
        embeddings = await embed_texts_async(
            texts_to_embed,
            task_type="RETRIEVAL_DOCUMENT",
            # We rely on default router construction here which picks up env vars
        )
    except Exception:
        logger.exception("Failed to generate embeddings for search index")
        return

    # 3. Construct Index
    # We map 1:1 between posts and embeddings
    search_index = []
    for i, post in enumerate(posts):
        vector = embeddings[i]

        # Optimization: Round floats to 4 decimals to save space
        short_vector = [round(x, 4) for x in vector]

        post["v"] = short_vector
        search_index.append(post)

    # 4. Write Artifact
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(search_index, f)

    logger.info("Generated search index with %d items at %s", len(search_index), output_path)
