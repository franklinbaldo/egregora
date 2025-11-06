"""Pydantic AI-powered editor agent with RAG and meta-LLM capabilities.

Autonomous post editing with line-by-line precision, RAG context queries,
and meta-LLM consultation for creative suggestions.

This is the Pydantic AI implementation of the editor agent. It replaces the
legacy google.genai implementation with a type-safe, testable agent using
Pydantic AI's tool calling and state management.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ibis
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

try:
    from pydantic_ai.models.google import GoogleModel
except ImportError:  # pragma: no cover - legacy SDKs
    from pydantic_ai.models.gemini import GeminiModel as GoogleModel  # type: ignore

from egregora.agents.editor.document import DocumentSnapshot, Editor
from egregora.agents.tools.rag import VectorStore, query_similar_posts
from egregora.config import ModelConfig
from egregora.prompt_templates import EditorPromptTemplate
from egregora.utils.batch import GeminiBatchClient
from egregora.utils.genai import call_with_retries
from egregora.utils.logfire_config import logfire_span

logger = logging.getLogger(__name__)


# Pydantic Models for Tool Results and Final Output


class EditLineResult(BaseModel):
    """Result of an edit_line operation."""

    success: bool
    message: str
    new_version: int | None = None


class FullRewriteResult(BaseModel):
    """Result of a full_rewrite operation."""

    success: bool
    message: str
    new_version: int | None = None


class QueryRAGResult(BaseModel):
    """Result of a query_rag operation."""

    results: list[dict[str, Any]] = Field(default_factory=list)
    summary: str


class AskLLMResult(BaseModel):
    """Result of an ask_llm operation."""

    answer: str


class FinishResult(BaseModel):
    """Result of a finish operation."""

    success: bool
    decision: str
    notes: str = ""


class EditorAgentResult(BaseModel):
    """Final result from the editor agent."""

    decision: str = Field(description="'publish' or 'hold'")
    notes: str = Field(default="", description="Editor notes or explanation")


# Agent State


@dataclass
class EditorAgentState:
    """State passed to editor agent tools."""

    editor: Editor
    rag_dir: Path
    client: Any  # genai.Client
    model_config: ModelConfig
    post_path: Path
    tool_calls_log: list[dict[str, Any]] = field(default_factory=list)


# Helper Functions


def markdown_to_snapshot(content: str, doc_id: str) -> DocumentSnapshot:
    """Convert markdown content to DocumentSnapshot."""
    lines = content.split("\n")
    return DocumentSnapshot(doc_id=doc_id, version=1, meta={}, lines=dict(enumerate(lines)))


def snapshot_to_markdown(snapshot: DocumentSnapshot) -> str:
    """Convert DocumentSnapshot back to markdown."""
    sorted_lines = [snapshot.lines[i] for i in sorted(snapshot.lines.keys())]
    return "\n".join(sorted_lines)


async def query_rag_impl(
    query: str,
    max_results: int,
    rag_dir: Path,
    client: Any,
    model_config: ModelConfig,
) -> QueryRAGResult:
    """RAG search implementation."""
    if not rag_dir.exists():
        return QueryRAGResult(results=[], summary="RAG system not available (no posts indexed yet)")

    try:
        store = VectorStore(rag_dir / "chunks.parquet")
        embedding_model = model_config.get_model("embedding")
        # Create a dummy table for query_similar_posts
        dummy_table = ibis.memtable({"query_text": [query]})

        results = await query_similar_posts(
            table=dummy_table,
            batch_client=GeminiBatchClient(client, default_model=embedding_model),
            store=store,
            embedding_model=embedding_model,
            top_k=max_results,
        )

        if not results:
            return QueryRAGResult(results=[], summary=f"No relevant results found for: {query}")

        # Format results
        result_dicts = [
            {
                "post_id": result.get("post_id", "unknown"),
                "similarity": float(result.get("similarity", 0)),
                "text": result.get("text", "")[:400],
            }
            for result in results
        ]

        summary = f"Found {len(result_dicts)} relevant results for: {query}"
        return QueryRAGResult(results=result_dicts, summary=summary)

    except Exception as e:
        logger.exception("RAG query failed")
        return QueryRAGResult(results=[], summary=f"RAG query failed: {e!s}")


async def ask_llm_impl(
    question: str,
    client: Any,
    model: str,
) -> AskLLMResult:
    """Simple Q&A with fresh LLM instance."""
    from google.genai import types as genai_types

    try:
        response = await call_with_retries(
            client.aio.models.generate_content,
            model=model,
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=question)],
                ),
            ],
            config=genai_types.GenerateContentConfig(temperature=0.7),
        )

        answer = (response.text or "No response").strip()
        return AskLLMResult(answer=answer)

    except Exception as e:
        logger.exception("ask_llm failed")
        return AskLLMResult(answer=f"[LLM query failed: {e!s}]")


# Tool Registration


def _register_editor_tools(agent: Agent) -> None:
    """Register all editor tools on the agent."""

    @agent.tool
    def edit_line_tool(
        ctx: RunContext[EditorAgentState],
        expect_version: int,
        index: int,
        new_text: str,
    ) -> EditLineResult:
        """Replace a single line in the document.

        Args:
            expect_version: Expected document version (for optimistic concurrency)
            index: Line index to edit (0-based)
            new_text: New content for this line

        """
        result_dict = ctx.deps.editor.edit_line(
            expect_version=expect_version,
            index=index,
            new=new_text,
        )

        ctx.deps.tool_calls_log.append(
            {"tool": "edit_line", "args": {"expect_version": expect_version, "index": index}},
        )

        if result_dict.get("ok"):
            return EditLineResult(
                success=True,
                message=f"Line {index} edited successfully",
                new_version=result_dict.get("version"),
            )
        return EditLineResult(
            success=False,
            message=result_dict.get("error", "Edit failed"),
            new_version=None,
        )

    @agent.tool
    def full_rewrite_tool(
        ctx: RunContext[EditorAgentState],
        expect_version: int,
        content: str,
    ) -> FullRewriteResult:
        """Replace the entire document content.

        Args:
            expect_version: Expected document version
            content: New complete document content

        """
        result_dict = ctx.deps.editor.full_rewrite(
            expect_version=expect_version,
            content=content,
        )

        ctx.deps.tool_calls_log.append({"tool": "full_rewrite", "args": {"expect_version": expect_version}})

        if result_dict.get("ok"):
            return FullRewriteResult(
                success=True,
                message="Document rewritten successfully",
                new_version=result_dict.get("version"),
            )
        return FullRewriteResult(
            success=False,
            message=result_dict.get("error", "Rewrite failed"),
            new_version=None,
        )

    @agent.tool
    async def query_rag_tool(
        ctx: RunContext[EditorAgentState],
        query: str,
        max_results: int = 5,
    ) -> QueryRAGResult:
        """Search past Egregora posts and enrichments for relevant context.

        Use this to find related discussions, definitions, or examples from previous posts.

        Args:
            query: Search query (e.g. 'consciousness emergence', 'AI alignment')
            max_results: Maximum results to return (default 5)

        """
        ctx.deps.tool_calls_log.append(
            {"tool": "query_rag", "args": {"query": query, "max_results": max_results}},
        )

        return await query_rag_impl(
            query=query,
            max_results=max_results,
            rag_dir=ctx.deps.rag_dir,
            client=ctx.deps.client,
            model_config=ctx.deps.model_config,
        )

    @agent.tool
    async def ask_llm_tool(
        ctx: RunContext[EditorAgentState],
        question: str,
    ) -> AskLLMResult:
        """Ask a separate LLM for ideas, clarification, or creative input.

        Use cases:
        - "What are good metaphors for X?"
        - "What are obscure facts about Y?"
        - "What else would you say about Z in this context?"
        - "Is this analogy scientifically accurate?"
        - "Suggest 3 alternative titles for this section"
        - "What's a clearer way to explain X?"

        Args:
            question: Question to ask the LLM

        """
        ctx.deps.tool_calls_log.append({"tool": "ask_llm", "args": {"question": question}})

        model = ctx.deps.model_config.get_model("editor")
        return await ask_llm_impl(
            question=question,
            client=ctx.deps.client,
            model=model,
        )


async def run_editor_session_with_pydantic_agent(  # noqa: PLR0913
    post_path: Path,
    client: Any,
    model_config: ModelConfig,
    rag_dir: Path,
    context: dict[str, Any] | None = None,
    max_turns: int = 15,
    agent_model: Any | None = None,
) -> dict[str, Any]:
    """Run a full editing session on a post using Pydantic AI agent.

    Args:
        post_path: Path to the post markdown file
        client: Gemini client
        model_config: Model configuration
        rag_dir: Path to RAG database
        context: Optional context (ELO score, ranking comments, etc.)
        max_turns: Maximum number of conversation turns
        agent_model: Optional test model for deterministic tests

    Returns:
        Dictionary with:
        - final_content: str - Final post content
        - decision: str - "publish" or "hold"
        - notes: str - Editor notes
        - edits_made: bool - Whether any edits were made
        - tool_calls: list - Log of tool calls

    """
    # Load post content
    if not post_path.exists():
        raise FileNotFoundError(f"Post not found: {post_path}")

    original_content = post_path.read_text(encoding="utf-8")
    snapshot = markdown_to_snapshot(original_content, doc_id=str(post_path))
    editor = Editor(snapshot)

    # Prepare initial prompt
    context = context or {}
    prompt = EditorPromptTemplate(
        post_content=original_content,
        doc_id=str(post_path),
        version=snapshot.version,
        lines=snapshot.lines,
        context=context,
    ).render()

    # Create agent state
    state = EditorAgentState(
        editor=editor,
        rag_dir=rag_dir,
        client=client,
        model_config=model_config,
        post_path=post_path,
        tool_calls_log=[],
    )

    # Create agent using our shared infrastructure
    model_name = model_config.get_model("editor")
    logger.info("[blue]✏️  Editor model:[/] %s", model_name)

    with logfire_span("editor_agent", post_path=str(post_path), model=model_name):
        # Create the agent
        agent = Agent[EditorAgentState, EditorAgentResult](
            model=agent_model or GoogleModel(model_name),
            deps_type=EditorAgentState,
            output_type=EditorAgentResult,
            system_prompt=f"""You are an autonomous editor for Egregora blog posts.

Your task: Review and improve the post, then decide if it's ready to publish or needs human review.

Current document version: {snapshot.version}
Document has {len(snapshot.lines)} lines.

When you're done, use the result to indicate your decision and notes.
""",
        )

        # Register tools
        _register_editor_tools(agent)

        try:
            # Run the agent
            result = await agent.run(prompt, deps=state)

            # Get final result
            final_result = result.output

            return {
                "final_content": snapshot_to_markdown(editor.snapshot),
                "decision": final_result.decision,
                "notes": final_result.notes,
                "edits_made": editor.snapshot.version > 1,
                "tool_calls": state.tool_calls_log,
            }

        except Exception as e:
            logger.exception("Editor agent failed")
            raise RuntimeError("Editor agent execution failed") from e
