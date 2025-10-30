"""LLM-powered editor agent with RAG and meta-LLM capabilities.

Autonomous post editing with line-by-line precision, RAG context queries,
and meta-LLM consultation for creative suggestions.

Documentation:
- Editor Feature: docs/features/editor.md
- API Reference: docs/reference/api.md#editor-agent
- CLI Reference: docs/reference/cli.md#egregora-edit
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types as genai_types

from .editor import DocumentSnapshot, Editor
from .gemini_batch import GeminiBatchClient
from .genai_utils import call_with_retries
from .model_config import ModelConfig
from .prompt_templates import render_editor_prompt
from .rag import VectorStore, query_similar_posts

logger = logging.getLogger(__name__)


@dataclass
class EditorResult:
    """Result of an editor session."""

    final_content: str
    decision: str  # "publish" or "hold"
    notes: str
    edits_made: bool
    tool_calls: list[dict[str, object]]  # Log of all tool calls made


class _QueryDataFrame:
    """Minimal pandas-like object used for embedding the query text."""

    def __init__(self, query: str) -> None:
        self._query = query

    def to_csv(
        self,
        path_or_buf: object | None = None,
        *,
        sep: str = "|",
        index: bool = False,
    ) -> str:
        return self._query


class _QueryCountResult:
    """Simple wrapper returning a row count via ``execute``."""

    def __init__(self, count: int) -> None:
        self._count = count

    def execute(self) -> int:
        return self._count


class _QueryTable:
    """Table-like wrapper compatible with ``query_similar_posts``."""

    def __init__(self, query: str) -> None:
        self._query = query

    def count(self) -> _QueryCountResult:
        return _QueryCountResult(1 if self._query else 0)

    def execute(self) -> _QueryDataFrame:
        return _QueryDataFrame(self._query)


def _coerce_int(value: Any, default: int) -> int:
    """Convert ``value`` to ``int`` while providing a safe fallback."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_str(value: Any, default: str = "") -> str:
    """Convert ``value`` to ``str`` while substituting ``default`` for ``None``."""

    if value is None:
        return default
    return str(value)


def _coerce_float(value: Any, default: float = 0.0) -> float:
    """Convert ``value`` to ``float`` with graceful fallback."""

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# Gemini Function Declarations for Editor Tools
EDIT_LINE_TOOL = genai_types.Tool(
    function_declarations=[
        genai_types.FunctionDeclaration(
            name="edit_line",
            description="Replace a single line in the document",
            parameters={
                "type": "object",
                "properties": {
                    "expect_version": {
                        "type": "integer",
                        "description": "Expected document version (for optimistic concurrency)",
                    },
                    "index": {"type": "integer", "description": "Line index to edit (0-based)"},
                    "new": {"type": "string", "description": "New content for this line"},
                },
                "required": ["expect_version", "index", "new"],
            },
        )
    ]
)

FULL_REWRITE_TOOL = genai_types.Tool(
    function_declarations=[
        genai_types.FunctionDeclaration(
            name="full_rewrite",
            description="Replace the entire document content",
            parameters={
                "type": "object",
                "properties": {
                    "expect_version": {
                        "type": "integer",
                        "description": "Expected document version",
                    },
                    "content": {"type": "string", "description": "New complete document content"},
                },
                "required": ["expect_version", "content"],
            },
        )
    ]
)

QUERY_RAG_TOOL = genai_types.Tool(
    function_declarations=[
        genai_types.FunctionDeclaration(
            name="query_rag",
            description="Search past Egregora posts and enrichments for relevant context. Use this to find related discussions, definitions, or examples from previous posts.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g. 'consciousness emergence', 'AI alignment', 'evolutionary psychology')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return (default 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        )
    ]
)

ASK_LLM_TOOL = genai_types.Tool(
    function_declarations=[
        genai_types.FunctionDeclaration(
            name="ask_llm",
            description="""Ask a separate LLM for ideas, clarification, or creative input.

Use cases:
- "What are good metaphors for X?"
- "What are obscure facts about Y?"
- "What else would you say about Z in this context?"
- "Is this analogy scientifically accurate?"
- "Suggest 3 alternative titles for this section"
- "What's a clearer way to explain X?"
""",
            parameters={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Question to ask the LLM"}
                },
                "required": ["question"],
            },
        )
    ]
)

FINISH_TOOL = genai_types.Tool(
    function_declarations=[
        genai_types.FunctionDeclaration(
            name="finish",
            description="Mark editing complete. Call this when satisfied with the post (with or without edits) or when it needs human review.",
            parameters={
                "type": "object",
                "properties": {
                    "expect_version": {
                        "type": "integer",
                        "description": "Expected document version",
                    },
                    "decision": {
                        "type": "string",
                        "enum": ["publish", "hold"],
                        "description": "publish: post is ready | hold: needs human review",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Summary of changes made or reason for holding",
                    },
                },
                "required": ["expect_version", "decision", "notes"],
            },
        )
    ]
)


def markdown_to_snapshot(content: str, doc_id: str) -> DocumentSnapshot:
    """Convert markdown content to DocumentSnapshot."""
    lines = content.split("\n")
    return DocumentSnapshot(
        doc_id=doc_id, version=1, meta={}, lines={i: line for i, line in enumerate(lines)}
    )


def snapshot_to_markdown(snapshot: DocumentSnapshot) -> str:
    """Convert DocumentSnapshot back to markdown."""
    sorted_lines = [snapshot.lines[i] for i in sorted(snapshot.lines.keys())]
    return "\n".join(sorted_lines)


async def _query_rag_tool(
    query: str,
    max_results: int,
    rag_dir: Path,
    client: genai.Client,
    model_config: ModelConfig,
) -> str:
    """RAG search returning formatted context string."""
    if not rag_dir.exists():
        return "RAG system not available (no posts indexed yet)"

    store_path = rag_dir / "chunks.parquet"
    if not store_path.exists():
        return "RAG system not available (no posts indexed yet)"

    embedding_model = model_config.get_model("embedding")
    batch_client = GeminiBatchClient(client, default_model=embedding_model)
    store = VectorStore(store_path)

    results_table = query_similar_posts(
        _QueryTable(query),
        batch_client,
        store,
        embedding_model=embedding_model,
        top_k=max_results,
        deduplicate=True,
        output_dimensionality=model_config.get_embedding_output_dimensionality(),
    )

    if results_table.count().execute() == 0:
        return f"No relevant results found for: {query}"

    results = results_table.execute().to_dict("records")

    # Format results for editor
    formatted = [f"RAG Results for '{query}':\n"]
    for i, result in enumerate(results, 1):
        post_label = (
            _coerce_str(result.get("post_title"))
            or _coerce_str(result.get("post_slug"))
            or _coerce_str(result.get("document_id"))
            or "unknown"
        )
        formatted.append(f"[{i}] Post: {post_label}")
        similarity = _coerce_float(result.get("similarity"), 0.0)
        formatted.append(f"    Similarity: {similarity:.2f}")
        excerpt = _coerce_str(result.get("content"))[:400]
        formatted.append(f"    Excerpt: {excerpt}...")
        formatted.append("")

    return "\n".join(formatted)


async def _ask_llm_tool(
    question: str,
    client: genai.Client,
    model: str,
) -> str:
    """Simple Q&A with fresh LLM instance."""
    try:
        response = await call_with_retries(
            client.aio.models.generate_content,
            model=model,
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=question)],
                )
            ],
            config=genai_types.GenerateContentConfig(temperature=0.7),
        )

        return (response.text or "No response").strip()

    except Exception as e:
        logger.error(f"ask_llm failed: {e}")
        return f"[LLM query failed: {str(e)}]"


async def run_editor_session(  # noqa: PLR0912, PLR0913, PLR0915
    post_path: Path,
    client: genai.Client,
    model_config: ModelConfig,
    rag_dir: Path,
    context: dict | None = None,
    max_turns: int = 15,
) -> EditorResult:
    """
    Run a full editing session on a post using LLM with editor tools.

    Args:
        post_path: Path to the post markdown file
        client: Gemini client
        model_config: Model configuration
        rag_dir: Path to RAG database
        context: Optional context (ELO score, ranking comments, etc.)

    Returns:
        EditorResult with final content, decision, and edit log
    """
    # Load post content
    if not post_path.exists():
        raise FileNotFoundError(f"Post not found: {post_path}")

    original_content = post_path.read_text(encoding="utf-8")
    snapshot = markdown_to_snapshot(original_content, doc_id=str(post_path))
    editor = Editor(snapshot)

    # Prepare initial prompt
    context = context or {}
    prompt = render_editor_prompt(
        post_content=original_content,
        doc_id=str(post_path),
        version=snapshot.version,
        lines=snapshot.lines,
        context=context,
    )

    # Initialize conversation
    conversation_history = [genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])]

    # All tools available
    tools = [
        EDIT_LINE_TOOL,
        FULL_REWRITE_TOOL,
        QUERY_RAG_TOOL,
        ASK_LLM_TOOL,
        FINISH_TOOL,
    ]

    model = model_config.get_model("editor")
    logger.info("[blue]✏️  Editor model:[/] %s", model)
    tool_calls_log: list[dict[str, object]] = []

    logger.info(f"Starting editor session for {post_path.name}")

    for turn in range(max_turns):
        logger.info(f"Editor turn {turn + 1}/{max_turns}")

        try:
            response = await call_with_retries(
                client.aio.models.generate_content,
                model=model,
                contents=conversation_history,
                config=genai_types.GenerateContentConfig(
                    temperature=0.5,
                    tools=tools,
                ),
            )

            # Add assistant response to history
            if response.candidates and response.candidates[0].content:
                conversation_history.append(response.candidates[0].content)

            # Process tool calls
            tool_responses = []

            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        fc_name = fc.name
                        fc_args: dict[str, Any] = dict(fc.args)

                        logger.info(f"Tool call: {fc_name}({fc_args})")
                        tool_calls_log.append({"tool": fc_name, "args": fc_args})

                        # Execute tool
                        if fc_name == "query_rag":
                            result_str = await _query_rag_tool(
                                query=_coerce_str(fc_args.get("query")),
                                max_results=_coerce_int(fc_args.get("max_results"), 5),
                                rag_dir=rag_dir,
                                client=client,
                                model_config=model_config,
                            )

                        elif fc_name == "ask_llm":
                            result_str = await _ask_llm_tool(
                                question=_coerce_str(fc_args.get("question")),
                                client=client,
                                model=model,
                            )

                        elif fc_name == "edit_line":
                            edit_result = editor.edit_line(
                                expect_version=_coerce_int(fc_args.get("expect_version"), 0),
                                index=_coerce_int(fc_args.get("index"), 0),
                                new=_coerce_str(fc_args.get("new")),
                            )
                            result_str = str(edit_result)

                        elif fc_name == "full_rewrite":
                            rewrite_result = editor.full_rewrite(
                                expect_version=_coerce_int(fc_args.get("expect_version"), 0),
                                content=_coerce_str(fc_args.get("content")),
                            )
                            result_str = str(rewrite_result)

                        elif fc_name == "finish":
                            finish_result = editor.finish(
                                expect_version=_coerce_int(fc_args.get("expect_version"), 0),
                                decision=_coerce_str(fc_args.get("decision"), "hold"),
                                notes=_coerce_str(fc_args.get("notes")),
                            )

                            # Check if finish was successful
                            if finish_result.get("ok"):
                                logger.info(f"Editor finished: {finish_result}")
                                return EditorResult(
                                    final_content=snapshot_to_markdown(editor.snapshot),
                                    decision=_coerce_str(finish_result.get("decision"), "hold"),
                                    notes=_coerce_str(finish_result.get("notes")),
                                    edits_made=editor.snapshot.version > 1,
                                    tool_calls=tool_calls_log,
                                )
                            result_str = str(finish_result)

                        else:
                            result_str = f"Unknown tool: {fc_name}"

                        # Add tool response to conversation
                        tool_responses.append(
                            genai_types.Part(
                                function_response=genai_types.FunctionResponse(
                                    name=fc_name, response={"result": result_str}
                                )
                            )
                        )

            # Add all tool responses to conversation
            if tool_responses:
                conversation_history.append(genai_types.Content(role="user", parts=tool_responses))
            else:
                # No tool calls and no finish - might be stuck
                logger.warning(f"Turn {turn + 1}: No tool calls detected")
                break

        except Exception as e:
            logger.error(f"Error in editor turn {turn + 1}: {e}")
            break

    # If we exit loop without finish() being called
    logger.warning("Editor session reached max turns without finishing")
    return EditorResult(
        final_content=snapshot_to_markdown(editor.snapshot),
        decision="hold",
        notes="Editor session incomplete (max turns reached)",
        edits_made=editor.snapshot.version > 1,
        tool_calls=tool_calls_log,
    )
