from pathlib import Path

import ibis
from google import genai

from egregora.agents.tools.rag import VectorStore, query_similar_posts
from egregora.config import ModelConfig
from egregora.utils.genai import call_with_retries


def edit_line(expect_version: int, index: int, new: str, editor) -> None:
    """Replace a single line in the document"""
    editor.edit_line(expect_version, index, new)


def full_rewrite(expect_version: int, content: str, editor) -> None:
    """Replace the entire document content"""
    editor.full_rewrite(expect_version, content)


async def query_rag(
    query: str,
    max_results: int,
    rag_dir: Path,
    client: genai.Client,
    model_config: ModelConfig,
) -> str:
    """RAG search returning formatted context string."""
    if not rag_dir.exists():
        return "RAG system not available (no posts indexed yet)"

    try:
        store = VectorStore(rag_dir / "chunks.parquet")
        embedding_model = model_config.get_model("embedding")
        dummy_table = ibis.memtable({"query_text": [query]})

        results = await query_similar_posts(
            table=dummy_table,
            client=client,
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

    except Exception as e:
        return f"RAG query failed: {e!s}"


async def ask_llm(
    question: str,
    client: genai.Client,
    model_config: ModelConfig,
) -> str:
    """Simple Q&A with fresh LLM instance."""
    try:
        model = model_config.get_model("editor")
        response = await call_with_retries(
            client.aio.models.generate_content,
            model=model,
            contents=[
                genai.types.Content(
                    role="user",
                    parts=[genai.types.Part(text=question)],
                )
            ],
            config=genai.types.GenerateContentConfig(temperature=0.7),
        )

        return (response.text or "No response").strip()

    except Exception as e:
        return f"[LLM query failed: {e!s}]"


def finish(expect_version: int, decision: str, notes: str) -> None:
    """Mark editing complete."""
    pass


def diversity_sampler(k: int, seed: int) -> str:
    """Sample diverse content based on a given seed."""
    return f"Sampled {k} items with seed {seed}."


def link_rewriter(url: str) -> str:
    """Rewrite a URL."""
    return f"Rewrote URL: {url}"


AVAILABLE_TOOLS = {
    "edit_line": edit_line,
    "full_rewrite": full_rewrite,
    "query_rag": query_rag,
    "ask_llm": ask_llm,
    "finish": finish,
    "diversity_sampler": diversity_sampler,
    "link_rewriter": link_rewriter,
}
