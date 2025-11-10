"""Pydantic AI-powered editor agent with RAG and meta-LLM capabilities.

Autonomous post editing with line-by-line precision, RAG context queries,
and meta-LLM consultation for creative suggestions.

This is the Pydantic AI implementation of the editor agent. It replaces the
legacy google.genai implementation with a type-safe, testable agent using
Pydantic AI's tool calling and state management.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import frontmatter
import ibis
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent, RunContext

from egregora.agents.banner import generate_banner_for_post
from egregora.agents.editor.document import DocumentSnapshot, Editor
from egregora.agents.shared.rag import VectorStore, query_similar_posts
from egregora.config import ModelConfig
from egregora.prompt_templates import EditorPromptTemplate
from egregora.utils.genai import call_with_retries
from egregora.utils.logfire_config import logfire_span

if TYPE_CHECKING:
    from google import genai
logger = logging.getLogger(__name__)


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


class BannerResult(BaseModel):
    """Result of a banner generation operation."""

    status: str
    path: str | None = None


class EditorAgentResult(BaseModel):
    """Final result from the editor agent."""

    decision: str = Field(description="'publish' or 'hold'")
    notes: str = Field(default="", description="Editor notes or explanation")


class EditorAgentState(BaseModel):
    """Immutable dependencies passed to editor agent tools.

    MODERN (Phase 1): This is now frozen to prevent mutation in tools.
    Tool call logging is handled by Pydantic-AI message history.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)
    editor: Editor
    rag_dir: Path
    prompts_dir: Path | None  # Custom prompts directory (e.g., site_root/.egregora/prompts)
    client: Any
    model_config_obj: ModelConfig
    post_path: Path


def markdown_to_snapshot(content: str, doc_id: str) -> DocumentSnapshot:
    """Convert markdown content to DocumentSnapshot."""
    lines = content.split("\n")
    return DocumentSnapshot(doc_id=doc_id, version=1, meta={}, lines=dict(enumerate(lines)))


def snapshot_to_markdown(snapshot: DocumentSnapshot) -> str:
    """Convert DocumentSnapshot back to markdown."""
    sorted_lines = [snapshot.lines[i] for i in sorted(snapshot.lines.keys())]
    return "\n".join(sorted_lines)


async def query_rag_impl(
    query: str, max_results: int, rag_dir: Path, _client: genai.Client, model_config: ModelConfig
) -> QueryRAGResult:
    """RAG search implementation."""
    if not rag_dir.exists():
        return QueryRAGResult(results=[], summary="RAG system not available (no posts indexed yet)")
    try:
        store = VectorStore(rag_dir / "chunks.parquet")
        embedding_model = model_config.get_model("embedding")
        dummy_table = ibis.memtable({"query_text": [query]})
        results = await query_similar_posts(
            table=dummy_table, store=store, embedding_model=embedding_model, top_k=max_results
        )
        if not results:
            return QueryRAGResult(results=[], summary=f"No relevant results found for: {query}")
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


async def ask_llm_impl(question: str, client: genai.Client, model: str) -> AskLLMResult:
    """Simple Q&A with fresh LLM instance."""
    from google.genai import types as genai_types  # noqa: PLC0415

    try:
        if ":" in model:
            model = model.split(":", 1)[1]
        if not model.startswith("models/"):
            model = f"models/{model}"
        response = await call_with_retries(
            client.aio.models.generate_content,
            model=model,
            contents=[genai_types.Content(role="user", parts=[genai_types.Part(text=question)])],
            config=genai_types.GenerateContentConfig(temperature=0.7),
        )
        answer = (response.text or "No response").strip()
        return AskLLMResult(answer=answer)
    except Exception as e:
        logger.exception("ask_llm failed")
        return AskLLMResult(answer=f"[LLM query failed: {e!s}]")


def _register_editor_tools(agent: Agent) -> None:  # noqa: C901
    """Register all editor tools on the agent."""

    @agent.tool
    def edit_line_tool(
        ctx: RunContext[EditorAgentState], expect_version: int, index: int, new_text: str
    ) -> EditLineResult:
        """Replace a single line in the document.

        Args:
            expect_version: Expected document version (for optimistic concurrency)
            index: Line index to edit (0-based)
            new_text: New content for this line

        """
        result_dict = ctx.deps.editor.edit_line(expect_version=expect_version, index=index, new=new_text)
        if result_dict.get("ok"):
            return EditLineResult(
                success=True,
                message=f"Line {index} edited successfully",
                new_version=result_dict.get("version"),
            )
        return EditLineResult(
            success=False, message=result_dict.get("error", "Edit failed"), new_version=None
        )

    @agent.tool
    def full_rewrite_tool(
        ctx: RunContext[EditorAgentState], expect_version: int, content: str
    ) -> FullRewriteResult:
        """Replace the entire document content.

        Args:
            expect_version: Expected document version
            content: New complete document content

        """
        result_dict = ctx.deps.editor.full_rewrite(expect_version=expect_version, content=content)
        if result_dict.get("ok"):
            return FullRewriteResult(
                success=True,
                message="Document rewritten successfully",
                new_version=result_dict.get("version"),
            )
        return FullRewriteResult(
            success=False, message=result_dict.get("error", "Rewrite failed"), new_version=None
        )

    @agent.tool
    async def query_rag_tool(
        ctx: RunContext[EditorAgentState], query: str, max_results: int = 5
    ) -> QueryRAGResult:
        """Search past Egregora posts and enrichments for relevant context.

        Use this to find related discussions, definitions, or examples from previous posts.

        Args:
            query: Search query (e.g. 'consciousness emergence', 'AI alignment')
            max_results: Maximum results to return (default 5)

        """
        return await query_rag_impl(
            query=query,
            max_results=max_results,
            rag_dir=ctx.deps.rag_dir,
            client=ctx.deps.client,
            model_config=ctx.deps.model_config_obj,
        )

    @agent.tool
    async def ask_llm_tool(ctx: RunContext[EditorAgentState], question: str) -> AskLLMResult:
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
        model = ctx.deps.model_config_obj.get_model("editor")
        return await ask_llm_impl(question=question, client=ctx.deps.client, model=model)

    @agent.tool
    def generate_banner_tool(ctx: RunContext[EditorAgentState]) -> BannerResult:
        """Generate a cover banner image for this post.

        Creates an AI-generated banner image based on the post's title and summary
        from its front matter. The banner will be saved in the same directory as
        the post.

        Returns:
            BannerResult with status and path to the generated banner

        """
        try:
            post = frontmatter.load(ctx.deps.post_path)
            title = post.get("title", "")
            summary = post.get("summary", "")
            slug = post.get("slug", ctx.deps.post_path.stem)
            if not title:
                return BannerResult(status="error", path=None)
            output_dir = ctx.deps.post_path.parent
            banner_path = generate_banner_for_post(
                post_title=title, post_summary=summary or title, output_dir=output_dir, slug=slug
            )
            if banner_path:
                return BannerResult(status="success", path=str(banner_path))
            return BannerResult(status="failed", path=None)
        except Exception:
            logger.exception("Banner generation failed in editor")
            return BannerResult(status="error", path=None)


async def run_editor_session_with_pydantic_agent(  # noqa: PLR0913
    post_path: Path,
    client: genai.Client,
    model_config: ModelConfig,
    rag_dir: Path,
    site_root: Path | None = None,
    context: dict[str, Any] | None = None,
    _max_turns: int = 15,
    agent_model: object | None = None,  # Test model injection - accepts any Pydantic AI compatible model
) -> dict[str, Any]:
    """Run a full editing session on a post using Pydantic AI agent.

    Args:
        post_path: Path to the post markdown file
        client: genai.Client instance
        model_config: Model configuration
        rag_dir: Path to RAG database
        site_root: Optional site root path for custom prompt overrides
        context: Optional context (ELO score, ranking comments, etc.)
        max_turns: Maximum number of conversation turns
        agent_model: Optional test model for deterministic tests

    Returns:
        Dictionary with:
        - final_content: str - Final post content
        - decision: str - "publish" or "hold"
        - notes: str - Editor notes
        - edits_made: bool - Whether any edits were made

    """
    if not post_path.exists():
        msg = f"Post not found: {post_path}"
        raise FileNotFoundError(msg)
    original_content = post_path.read_text(encoding="utf-8")
    snapshot = markdown_to_snapshot(original_content, doc_id=str(post_path))
    editor = Editor(snapshot)

    context = context or {}
    # Resolve prompts directory (site_root parameter is for backward compatibility)
    prompts_dir = site_root / ".egregora" / "prompts" if site_root and (site_root / ".egregora" / "prompts").is_dir() else None

    prompt = EditorPromptTemplate(
        post_content=original_content,
        doc_id=str(post_path),
        version=snapshot.version,
        lines=snapshot.lines,
        context=context,
        prompts_dir=prompts_dir,
    ).render()
    state = EditorAgentState(
        editor=editor,
        rag_dir=rag_dir,
        prompts_dir=prompts_dir,
        client=client,
        model_config_obj=model_config,
        post_path=post_path,
    )
    model_name = model_config.get_model("editor")
    logger.info("[blue]✏️  Editor model:[/] %s", model_name)
    with logfire_span("editor_agent", post_path=str(post_path), model=model_name):
        if agent_model is None:
            model = model_name
        else:
            model = agent_model
        agent = Agent[EditorAgentState, EditorAgentResult](
            model=model, deps_type=EditorAgentState, output_type=EditorAgentResult
        )

        @agent.system_prompt
        def editor_system_prompt(ctx: RunContext[EditorAgentState]) -> str:
            """Generate system prompt from template."""
            template = EditorPromptTemplate(
                post_content=snapshot_to_markdown(ctx.deps.editor.snapshot),
                doc_id=ctx.deps.post_path.stem,
                version=ctx.deps.editor.snapshot.version,
                lines=ctx.deps.editor.snapshot.lines,
                prompts_dir=ctx.deps.prompts_dir,
            )
            return template.render()

        _register_editor_tools(agent)
        try:
            result = await agent.run(prompt, deps=state)
            final_result = result.output
            return {
                "final_content": snapshot_to_markdown(editor.snapshot),
                "decision": final_result.decision,
                "notes": final_result.notes,
                "edits_made": editor.snapshot.version > 1,
            }
        except Exception as e:
            logger.exception("Editor agent failed")
            msg = "Editor agent execution failed"
            raise RuntimeError(msg) from e
