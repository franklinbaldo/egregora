"""Shared LLM helper functions exposed to interactive agents."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

import ibis
from google import genai

from egregora.agents.shared.rag import VectorStore, query_similar_posts
from egregora.config import get_model_for_task
from egregora.config.settings import EgregoraConfig
from egregora.utils.genai import call_with_retries

Tool = Callable[..., Awaitable[str]]


async def query_rag(
    query: str,
    max_results: int,
    rag_dir: Path,
    _client: genai.Client,
    egregora_config: EgregoraConfig | None,
    cli_model: str | None,
) -> str:
    """Return formatted RAG context for ``query``.

    Falls back to informative status messages when the index is missing or
    the similarity search fails.
    """

    if not rag_dir.exists():
        return "RAG system not available (no posts indexed yet)"

    try:
        store = VectorStore(rag_dir / "chunks.parquet")
        embedding_model = get_model_for_task("embedding", egregora_config, cli_model)
        dummy_table = ibis.memtable({"query_text": [query]})
        results = await query_similar_posts(
            table=dummy_table,
            store=store,
            embedding_model=embedding_model,
            top_k=max_results,
        )
        if not results:
            return f"No relevant results found for: {query}"

        formatted = [f"RAG Results for '{query}':\n"]
        for i, result in enumerate(results, 1):
            formatted.append(f"[{i}] Post: {result.get('post_id', 'unknown')}")
            formatted.append(f"    Similarity: {result.get('similarity', 0):.2f}")
            formatted.append(f"    Excerpt: {result.get('text', '')[:400]}...")
            formatted.append("")
        return "\n".join(formatted)
    except (ValueError, TypeError, AttributeError, OSError, RuntimeError) as exc:
        return f"RAG query failed: {exc!s}"


async def ask_llm(
    question: str,
    client: genai.Client,
    egregora_config: EgregoraConfig | None,
    cli_model: str | None,
) -> str:
    """Ask the configured editor model a free-form question."""

    try:
        model_google = get_model_for_task("editor", egregora_config, cli_model)
        if ":" in model_google:
            model_google = model_google.split(":", 1)[1]
        if not model_google.startswith("models/"):
            model_google = f"models/{model_google}"

        response = await call_with_retries(
            client.aio.models.generate_content,
            model=model_google,
            contents=[genai.types.Content(role="user", parts=[genai.types.Part(text=question)])],
            config=genai.types.GenerateContentConfig(temperature=0.7),
        )
        return (response.text or "No response").strip()
    except (ValueError, TypeError, AttributeError, OSError, RuntimeError) as exc:
        return f"[LLM query failed: {exc!s}]"


AVAILABLE_TOOLS: dict[str, Tool] = {
    "query_rag": query_rag,
    "ask_llm": ask_llm,
}
