"""LLM-powered editor agent with RAG and meta-LLM capabilities.

Autonomous post editing with line-by-line precision, RAG context queries,
and meta-LLM consultation for creative suggestions.

Documentation:
- Editor Feature: docs/features/editor.md
- API Reference: docs/reference/api.md#editor-agent
- CLI Reference: docs/reference/cli.md#egregora-edit
"""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ibis
from google import genai
from google.genai import types as genai_types
from jinja2 import Environment, FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment
from ...agents.resolver import AgentResolver
from ...agents.registry import ToolRegistry, SkillRegistry
from ...config import ModelConfig
from ...knowledge.rag import VectorStore, query_similar_posts
from ...utils.batch import GeminiBatchClient
from ...utils.genai import call_with_retries
from .document import DocumentSnapshot, Editor

logger = logging.getLogger(__name__)


@dataclass
class EditorResult:
    """Result of an editor session."""

    final_content: str
    decision: str  # "publish" or "hold"
    notes: str
    edits_made: bool
    tool_calls: list[dict[str, Any]]  # Log of all tool calls made


# Gemini Function Declarations for Editor Tools
AVAILABLE_TOOLS = {
    "edit_line": genai_types.Tool(
        function_declarations=[
            genai_types.FunctionDeclaration(
                name="edit_line",
                description="Replace a single line in the document",
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        "expect_version": genai_types.Schema(
                            type=genai_types.Type.INTEGER,
                            description="Expected document version (for optimistic concurrency)",
                        ),
                        "index": genai_types.Schema(
                            type=genai_types.Type.INTEGER, description="Line index to edit (0-based)"
                        ),
                        "new": genai_types.Schema(
                            type=genai_types.Type.STRING, description="New content for this line"
                        ),
                    },
                    required=["expect_version", "index", "new"],
                ),
            )
        ]
    ),
    "full_rewrite": genai_types.Tool(
        function_declarations=[
            genai_types.FunctionDeclaration(
                name="full_rewrite",
                description="Replace the entire document content",
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        "expect_version": genai_types.Schema(
                            type=genai_types.Type.INTEGER,
                            description="Expected document version",
                        ),
                        "content": genai_types.Schema(
                            type=genai_types.Type.STRING, description="New complete document content"
                        ),
                    },
                    required=["expect_version", "content"],
                ),
            )
        ]
    ),
    "query_rag": genai_types.Tool(
        function_declarations=[
            genai_types.FunctionDeclaration(
                name="query_rag",
                description="Search past Egregora posts and enrichments for relevant context. Use this to find related discussions, definitions, or examples from previous posts.",
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        "query": genai_types.Schema(
                            type=genai_types.Type.STRING,
                            description="Search query (e.g. 'consciousness emergence', 'AI alignment', 'evolutionary psychology')",
                        ),
                        "max_results": genai_types.Schema(
                            type=genai_types.Type.INTEGER,
                            description="Maximum results to return (default 5)",
                            default=5,
                        ),
                    },
                    required=["query"],
                ),
            )
        ]
    ),
    "ask_llm": genai_types.Tool(
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
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        "question": genai_types.Schema(
                            type=genai_types.Type.STRING, description="Question to ask the LLM"
                        )
                    },
                    required=["question"],
                ),
            )
        ]
    ),
    "finish": genai_types.Tool(
        function_declarations=[
            genai_types.FunctionDeclaration(
                name="finish",
                description="Mark editing complete. Call this when satisfied with the post (with or without edits) or when it needs human review.",
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        "expect_version": genai_types.Schema(
                            type=genai_types.Type.INTEGER,
                            description="Expected document version",
                        ),
                        "decision": genai_types.Schema(
                            type=genai_types.Type.STRING,
                            enum=["publish", "hold"],
                            description="publish: post is ready | hold: needs human review",
                        ),
                    },
                    required=["expect_version", "decision"],
                ),
            )
        ]
    ),
    "diversity_sampler": genai_types.Tool(
        function_declarations=[
            genai_types.FunctionDeclaration(
                name="diversity_sampler",
                description="Sample diverse content based on a given seed.",
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        "k": genai_types.Schema(type=genai_types.Type.INTEGER),
                        "seed": genai_types.Schema(type=genai_types.Type.INTEGER),
                    },
                    required=["k", "seed"],
                ),
            )
        ]
    ),
    "link_rewriter": genai_types.Tool(
        function_declarations=[
            genai_types.FunctionDeclaration(
                name="link_rewriter",
                description="Rewrite a URL.",
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={"url": genai_types.Schema(type=genai_types.Type.STRING)},
                    required=["url"],
                ),
            )
        ]
    ),
}


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

    try:
        store = VectorStore(rag_dir / "chunks.parquet")
        embedding_model = model_config.get_model("embedding")
        # Create a dummy table for query_similar_posts
        dummy_table = ibis.memtable({"query_text": [query]})

        results = await query_similar_posts(
            table=dummy_table,
            batch_client=GeminiBatchClient(
                client, default_model=model_config.get_model("embedding")
            ),
            store=store,
            embedding_model=embedding_model,
            top_k=max_results,
        )

        if not results:
            return f"No relevant results found for: {query}"

        # Format results for editor
        formatted = [f"RAG Results for '{query}':\n"]
        for i, result in enumerate(results, 1):
            formatted.append(f"[{i}] Post: {result.get('post_id', 'unknown')}")
            formatted.append(f"    Similarity: {result.get('similarity', 0):.2f}")
            formatted.append(f"    Excerpt: {result.get('text', '')[:400]}...")
            formatted.append("")

        return "\n".join(formatted)

    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        return f"RAG query failed: {str(e)}"


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
    egregora_path: Path,
    docs_path: Path,
    context: dict[str, Any] | None = None,
    max_turns: int = 15,
    agent_override: str | None = None,
) -> EditorResult:
    """
    Run a full editing session on a post using LLM with editor tools.

    Args:
        post_path: Path to the post markdown file
        client: Gemini client
        model_config: Model configuration
        rag_dir: Path to RAG database
        egregora_path: Path to the .egregora directory
        docs_path: Path to the docs directory
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

    # Initialize new components
    resolver = AgentResolver(egregora_path, docs_path)
    tool_registry = ToolRegistry(egregora_path)
    skill_registry = SkillRegistry(egregora_path)
    jinja_env = SandboxedEnvironment(loader=FileSystemLoader(str(egregora_path)))

    # Resolve agent and variables
    agent_config, final_vars = resolver.resolve(post_path, agent_override)

    # Render the prompt
    render_context = final_vars.copy()
    render_context.update({
        "doc_id": str(post_path),
        "version": snapshot.version,
        "lines": snapshot.lines,
        "context": context or {},
        "env": agent_config.env
    })

    template = jinja_env.from_string(agent_config.prompt_template)
    prompt = template.render(render_context)

    # Resolve toolset
    enabled_tool_names = tool_registry.resolve_toolset(agent_config.tools)
    tools = [AVAILABLE_TOOLS[name] for name in enabled_tool_names if name in AVAILABLE_TOOLS]

    # Calculate hashes
    agent_hash = tool_registry.get_agent_hash(agent_config)
    toolset_hash = tool_registry.get_toolset_hash(enabled_tool_names)
    skillset_hash = skill_registry.get_skillset_hash(agent_config.skills.get("enable", []))
    prompt_render_hash = hashlib.sha256(prompt.encode()).hexdigest()

    logger.info(f"Using agent: {agent_config.agent_id} ({agent_hash})")
    logger.info(f"Toolset hash: {toolset_hash}")
    logger.info(f"Skillset hash: {skillset_hash}")
    logger.info(f"Prompt hash: {prompt_render_hash}")

    # Initialize conversation
    conversation_history = [genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])]

    model = agent_config.model
    logger.info("[blue]✏️  Editor model:[/] %s", model)
    tool_calls_log = []

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
                        fc_args = dict(fc.args)

                        logger.info(f"Tool call: {fc_name}({fc_args})")
                        tool_calls_log.append({"tool": fc_name, "args": fc_args})

                        # Execute tool
                        result_str = ""
                        result_dict = {}
                        if fc_name == "query_rag":
                            result_str = await _query_rag_tool(
                                query=fc_args.get("query", ""),
                                max_results=fc_args.get("max_results", 5),
                                rag_dir=rag_dir,
                                client=client,
                                model_config=model_config,
                            )

                        elif fc_name == "ask_llm":
                            result_str = await _ask_llm_tool(
                                question=fc_args.get("question", ""),
                                client=client,
                                model=model,
                            )

                        elif fc_name == "edit_line":
                            result_dict = editor.edit_line(
                                expect_version=fc_args.get("expect_version", 0),
                                index=fc_args.get("index", 0),
                                new=fc_args.get("new", ""),
                            )
                            result_str = str(result_dict)

                        elif fc_name == "full_rewrite":
                            result_dict = editor.full_rewrite(
                                expect_version=fc_args.get("expect_version", 0),
                                content=fc_args.get("content", ""),
                            )
                            result_str = str(result_dict)

                        elif fc_name == "diversity_sampler":
                            # Placeholder implementation
                            result_str = f"Sampled {fc_args.get('k')} items with seed {fc_args.get('seed')}."

                        elif fc_name == "link_rewriter":
                            # Placeholder implementation
                            result_str = f"Rewrote URL: {fc_args.get('url')}"

                        elif fc_name == "finish":
                            result_dict = editor.finish(
                                expect_version=fc_args.get("expect_version", 0),
                                decision=fc_args.get("decision", "hold"),
                                notes=fc_args.get("notes", ""),
                            )

                            # Check if finish was successful
                            if result_dict.get("ok"):
                                logger.info(f"Editor finished: {result_dict}")
                                return EditorResult(
                                    final_content=snapshot_to_markdown(editor.snapshot),
                                    decision=result_dict.get("decision", "hold"),
                                    notes=result_dict.get("notes", ""),
                                    edits_made=editor.snapshot.version > 1,
                                    tool_calls=tool_calls_log,
                                )
                            else:
                                result_str = str(result_dict)

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
