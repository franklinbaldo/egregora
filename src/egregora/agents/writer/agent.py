"""Pydantic-AI powered writer agent.

This module implements the writer workflow using Pydantic-AI.
It exposes ``write_posts_with_pydantic_agent`` which mirrors the signature of
``write_posts_for_window`` but routes the LLM conversation through a
``pydantic_ai.Agent`` instance. The implementation keeps the existing tool
surface (write_post, read/write_profile, search_media, annotate, banner)
so the rest of the pipeline can remain unchanged during the migration.

MODERN (Phase 1): Deps are frozen/immutable, no mutation in tools.
MODERN (Phase 2): Uses WriterAgentContext to reduce parameters.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, ConfigDict, Field
from .schemas import (
    PostMetadata,
    WritePostResult,
    ReadProfileResult,
    WriteProfileResult,
    MediaItem,
    SearchMediaResult,
    AnnotationResult,
    BannerResult,
    WriterAgentReturn,
    WriterAgentState,
)

try:
    from pydantic_ai import Agent, ModelMessagesTypeAdapter, RunContext
except ImportError:
    from pydantic_ai import Agent, RunContext

    class ModelMessagesTypeAdapter:
        """Lightweight shim mirroring the adapter interface used in tests."""

        @staticmethod
        def dump_json(messages: object) -> str:
            if hasattr(messages, "model_dump_json"):
                return messages.model_dump_json(indent=2)
            if hasattr(messages, "model_dump"):
                return json.dumps(messages.model_dump(mode="json"), indent=2)
            if hasattr(messages, "to_json"):
                return messages.to_json(indent=2)
            return json.dumps(messages, indent=2, default=str)


from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)

from egregora.agents.banner import generate_banner_for_post, is_banner_generation_available
from egregora.agents.shared.annotations import AnnotationStore
from egregora.agents.shared.rag import VectorStore, is_rag_available, query_media
from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import OutputAdapter, UrlContext, UrlConvention

if TYPE_CHECKING:
    from pydantic_ai.result import RunResult

logger = logging.getLogger(__name__)

# Type aliases for improved type safety
# Note: Some types remain as Any due to Pydantic limitations with Protocol validation
MessageHistory = Sequence[ModelRequest | ModelResponse]
LLMClient = Any  # Could be various client types (Google, Anthropic, etc.)
AgentModel = Any  # Model specification (string or configured model object)


@dataclass(frozen=True, slots=True)
class WriterAgentContext:
    """Runtime context for writer agent execution."""

    start_time: datetime
    end_time: datetime
    url_convention: UrlConvention
    url_context: UrlContext
    output_format: OutputAdapter
    rag_store: VectorStore
    annotations_store: AnnotationStore | None
    client: LLMClient
    prompts_dir: Path | None = None


def _extract_thinking_content(messages: MessageHistory) -> list[str]:
    """Extract thinking/reasoning content from agent message history.

    Parses ModelResponse messages to find ThinkingPart objects containing
    the model's step-by-step reasoning process.

    Args:
        messages: Agent message history from result.all_messages()

    Returns:
        List of thinking content strings

    """
    thinking_contents: list[str] = []

    for message in messages:
        # Check if this is a ModelResponse message
        if isinstance(message, ModelResponse):
            # Iterate through parts to find ThinkingPart
            thinking_contents.extend(part.content for part in message.parts if isinstance(part, ThinkingPart))

    return thinking_contents


def _extract_journal_content(messages: MessageHistory) -> str:
    """Extract journal content from agent message history.

    Journal content is plain text output from the model that's NOT a tool call.
    This is typically the model's continuity journal / reflection memo.

    Args:
        messages: Agent message history from result.all_messages()

    Returns:
        Combined journal content as a single string

    """
    journal_parts: list[str] = []

    for message in messages:
        # Check if this is a ModelResponse message
        if isinstance(message, ModelResponse):
            # Iterate through parts to find TextPart (non-tool text output)
            journal_parts.extend(part.content for part in message.parts if isinstance(part, TextPart))

    return "\n\n".join(journal_parts).strip()


@dataclass(frozen=True)
class JournalEntry:
    """Represents a single entry in the intercalated journal log.

    Each entry is one of: thinking, journal text, or tool usage.
    Entries preserve the actual execution order from the agent's message history.
    """

    entry_type: str  # "thinking", "journal", "tool_call", "tool_return"
    content: str
    timestamp: datetime | None = None
    tool_name: str | None = None


def _extract_intercalated_log(messages: MessageHistory) -> list[JournalEntry]:
    """Extract intercalated journal log preserving actual execution order.

    Processes agent message history to create a timeline showing:
    - Model thinking/reasoning
    - Journal text output
    - Tool calls and their returns

    Args:
        messages: Agent message history from result.all_messages()

    Returns:
        List of JournalEntry objects in chronological order

    """
    entries: list[JournalEntry] = []

    for message in messages:
        # Handle ModelResponse (contains thinking and journal output)
        if isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, ThinkingPart):
                    entries.append(
                        JournalEntry(
                            entry_type="thinking",
                            content=part.content,
                            timestamp=getattr(message, "timestamp", None),
                        )
                    )
                elif isinstance(part, TextPart):
                    entries.append(
                        JournalEntry(
                            entry_type="journal",
                            content=part.content,
                            timestamp=getattr(message, "timestamp", None),
                        )
                    )
                elif isinstance(part, ToolCallPart):
                    # Format tool call
                    args_str = json.dumps(part.args, indent=2) if hasattr(part, "args") else "{}"
                    tool_call_content = f"Tool: {part.tool_name}\nArguments:\n{args_str}"
                    entries.append(
                        JournalEntry(
                            entry_type="tool_call",
                            content=tool_call_content,
                            timestamp=getattr(message, "timestamp", None),
                            tool_name=part.tool_name,
                        )
                    )
                elif isinstance(part, ToolReturnPart):
                    # Format tool return
                    result_str = str(part.content) if hasattr(part, "content") else "No result"
                    tool_return_content = f"Result: {result_str}"
                    entries.append(
                        JournalEntry(
                            entry_type="tool_return",
                            content=tool_return_content,
                            timestamp=getattr(message, "timestamp", None),
                            tool_name=getattr(part, "tool_name", None),
                        )
                    )

        # Handle ModelRequest (contains tool calls from model side)
        elif isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, ToolCallPart):
                    args_str = json.dumps(part.args, indent=2) if hasattr(part, "args") else "{}"
                    tool_call_content = f"Tool: {part.tool_name}\nArguments:\n{args_str}"
                    entries.append(
                        JournalEntry(
                            entry_type="tool_call",
                            content=tool_call_content,
                            timestamp=getattr(message, "timestamp", None),
                            tool_name=part.tool_name,
                        )
                    )

    return entries


def _save_journal_to_file(
    intercalated_log: list[JournalEntry],
    window_label: str,
    output_format: OutputAdapter,
) -> str | None:
    """Save journal entry with intercalated thinking, freeform, and tool usage to markdown file.

    Args:
        intercalated_log: List of journal entries in chronological order
        window_label: Human-readable window identifier (e.g., "2025-01-15 10:00 to 12:00")
        output_format: OutputAdapter instance for document persistence

    Returns:
        Journal identifier (opaque string), or None if no content

    """
    # Skip if no content at all
    if not intercalated_log:
        return None

    # Load template from templates directory
    templates_dir = Path(__file__).parent.parent.parent / "templates"
    if not templates_dir.exists():
        logger.warning("Templates directory not found: %s", templates_dir)
        return None

    try:
        env = Environment(
            loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape(enabled_extensions=())
        )
        template = env.get_template("journal.md.jinja")
    except (OSError, ValueError):  # TemplateNotFound, file I/O errors
        logger.exception("Failed to load journal template")
        return None

    # Render journal content
    now_utc = datetime.now(tz=UTC)
    try:
        journal_content = template.render(
            window_label=window_label,
            date=now_utc.strftime("%Y-%m-%d"),
            created=now_utc.isoformat(),
            intercalated_log=intercalated_log,
        )
    except (TypeError, ValueError):  # Template rendering errors
        logger.exception("Failed to render journal template")
        return None

    # Write using OutputAdapter
    try:
        doc = Document(
            content=journal_content,
            type=DocumentType.JOURNAL,
            metadata={"window_label": window_label, "date": now_utc.strftime("%Y-%m-%d")},
            source_window=window_label,
        )
        output_format.serve(doc)
        logger.info("Saved journal entry: %s", doc.document_id)
        return doc.document_id
    except Exception:  # Broad catch: journal is non-critical, various backends may raise different exceptions
        logger.exception("Failed to write journal for window %s", window_label)
        return None


def _parse_content_to_dict(content: Any) -> dict[str, Any] | None:
    """Parse tool result content into a dictionary.

    Handles multiple content formats:
    - JSON strings
    - Pydantic models with model_dump()
    - Objects with __dict__
    - Raw dictionaries

    Args:
        content: Content to parse (Any type needed: str, Pydantic model, dict, or arbitrary object)

    Returns:
        Parsed dictionary or None if parsing fails

    """
    if isinstance(content, str):
        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return None
    if hasattr(content, "model_dump"):
        return content.model_dump()
    if hasattr(content, "__dict__"):
        return vars(content)
    if isinstance(content, dict):
        return content
    return None


def _categorize_tool_result(tool_name: str | None, doc_id: str) -> tuple[str | None, str]:
    """Determine if tool result is a post or profile.

    Uses tool name first, falls back to path heuristics for legacy messages.

    Args:
        tool_name: Tool name if available (e.g., "write_post_tool")
        doc_id: Document ID/path string

    Returns:
        Tuple of ("post"|"profile"|None, doc_id). None if type cannot be determined.

    """
    # Primary: Use tool name
    if tool_name == "write_post_tool":
        return ("post", doc_id)
    if tool_name == "write_profile_tool":
        return ("profile", doc_id)

    # Fallback: Use path heuristics for legacy messages
    if "/posts/" in doc_id or doc_id.endswith(".md"):
        return ("post", doc_id)
    if "/profiles/" in doc_id:
        return ("profile", doc_id)

    return (None, doc_id)


def _extract_from_success_result(data: dict[str, Any], tool_name: str | None) -> tuple[list[str], list[str]]:
    """Extract document IDs from a successful tool result dictionary.

    Args:
        data: Parsed tool result dictionary
        tool_name: Tool name (used to categorize result)

    Returns:
        Tuple of (saved_posts, saved_profiles)

    """
    saved_posts: list[str] = []
    saved_profiles: list[str] = []

    if data.get("status") == "success" and "path" in data:
        doc_id = data["path"]
        result_type, doc_id = _categorize_tool_result(tool_name, doc_id)

        if result_type == "post":
            saved_posts.append(doc_id)
        elif result_type == "profile":
            saved_profiles.append(doc_id)

    return (saved_posts, saved_profiles)


def _extract_from_tool_return_part(part: ToolReturnPart) -> tuple[list[str], list[str]]:
    """Extract document IDs from a ToolReturnPart message.

    Args:
        part: ToolReturnPart with parsed result

    Returns:
        Tuple of (saved_posts, saved_profiles)

    """
    parsed = _parse_content_to_dict(part.content)
    if parsed is None:
        return ([], [])

    return _extract_from_success_result(parsed, part.tool_name)


def _extract_from_legacy_tool_return(message: Any) -> tuple[list[str], list[str]]:
    """Extract document IDs from legacy tool-return message.

    Args:
        message: Legacy tool-return message with kind="tool-return"
                 (Any type needed: legacy messages have arbitrary structure)

    Returns:
        Tuple of (saved_posts, saved_profiles)

    """
    parsed = _parse_content_to_dict(message.content)
    if parsed is None:
        return ([], [])

    tool_name = getattr(message, "tool_name", None)
    return _extract_from_success_result(parsed, tool_name)


def _extract_tool_results(messages: MessageHistory) -> tuple[list[str], list[str]]:
    """Extract saved post and profile document IDs from agent message history.

    Parses the agent's tool call results to find WritePostResult and
    WriteProfileResult returns. Uses tool names to distinguish document types
    instead of parsing filesystem paths (supports opaque document IDs).

    Args:
        messages: Agent message history from result.all_messages()

    Returns:
        Tuple of (saved_posts, saved_profiles) as lists of document IDs

    """
    saved_posts: list[str] = []
    saved_profiles: list[str] = []

    try:
        for message in messages:
            # Handle ModelResponse messages with parts
            if hasattr(message, "parts"):
                for part in message.parts:
                    if isinstance(part, ToolReturnPart):
                        posts, profiles = _extract_from_tool_return_part(part)
                        saved_posts.extend(posts)
                        saved_profiles.extend(profiles)

            # Handle legacy tool-return messages
            elif hasattr(message, "kind") and message.kind == "tool-return":
                posts, profiles = _extract_from_legacy_tool_return(message)
                saved_posts.extend(posts)
                saved_profiles.extend(profiles)

    except (AttributeError, TypeError) as e:
        logger.debug("Could not parse tool results: %s", e)

    return (saved_posts, saved_profiles)


from .tools import register_writer_tools


def _create_writer_agent_state(context: WriterAgentContext, config: EgregoraConfig) -> WriterAgentState:
    """Creates a WriterAgentState from the given context and config."""
    window_label = f"{context.start_time:%Y-%m-%d %H:%M} to {context.end_time:%H:%M}"
    return WriterAgentState(
        window_id=window_label,
        url_convention=context.url_convention,
        url_context=context.url_context,
        output_format=context.output_format,
        rag_store=context.rag_store,
        annotations_store=context.annotations_store,
        batch_client=context.client,
        embedding_model=config.models.embedding,
        retrieval_mode=config.rag.mode,
        retrieval_nprobe=config.rag.nprobe,
        retrieval_overfetch=config.rag.overfetch,
    )

def _setup_agent_and_state(
    config: EgregoraConfig,
    context: WriterAgentContext,
    test_model: AgentModel | None = None,
) -> tuple[Agent[WriterAgentState, WriterAgentReturn], WriterAgentState, str]:
    """Set up writer agent and execution state."""
    model_name = test_model if test_model is not None else config.models.writer
    agent = Agent[WriterAgentState, WriterAgentReturn](model=model_name, deps_type=WriterAgentState)
    register_writer_tools(agent, enable_banner=is_banner_generation_available(), enable_rag=is_rag_available())

    state = _create_writer_agent_state(context, config)
    window_label = f"{context.start_time:%Y-%m-%d %H:%M} to {context.end_time:%H:%M}"

    return agent, state, window_label


def _validate_prompt_fits(
    prompt: str,
    model_name: str,
    config: EgregoraConfig,
    window_label: str,
) -> None:
    """Validate prompt fits within model context window limits.

    Args:
        prompt: System prompt to validate
        model_name: Name of the LLM model
        config: Egregora configuration with token limits
        window_label: Window identifier for logging

    Raises:
        PromptTooLargeError: If prompt exceeds hard model limit

    """
    from egregora.agents.model_limits import (
        PromptTooLargeError,
        get_model_context_limit,
        validate_prompt_fits,
    )

    max_prompt_tokens = getattr(config.pipeline, "max_prompt_tokens", 100_000)
    use_full_context_window = getattr(config.pipeline, "use_full_context_window", False)

    fits, estimated_tokens, effective_limit = validate_prompt_fits(
        prompt,
        model_name,
        max_prompt_tokens=max_prompt_tokens,
        use_full_context_window=use_full_context_window,
    )

    if not fits:
        model_limit = get_model_context_limit(model_name)
        model_effective_limit = int(model_limit * 0.9)

        if estimated_tokens <= model_effective_limit:
            logger.warning(
                "Prompt exceeds %dk cap (%d tokens) but fits in model limit (%d tokens) for %s (window: %s) - allowing as exception (likely single large message)",
                max_prompt_tokens // 1000,
                estimated_tokens,
                model_effective_limit,
                model_name,
                window_label,
            )
        else:
            logger.error(
                "Prompt exceeds model hard limit: %d tokens > %d limit for %s (window: %s) - will split window",
                estimated_tokens,
                model_effective_limit,
                model_name,
                window_label,
            )
            raise PromptTooLargeError(
                estimated_tokens=estimated_tokens,
                effective_limit=model_effective_limit,
                model_name=model_name,
                window_id=window_label,
            )
    else:
        logger.info(
            "Prompt fits: %d tokens / %d limit (%.1f%% usage) for %s",
            estimated_tokens,
            effective_limit,
            (estimated_tokens / effective_limit) * 100,
            model_name,
        )


def _run_agent_with_retries(
    agent: Agent[WriterAgentState, WriterAgentReturn],
    state: WriterAgentState,
    prompt: str,
) -> RunResult[WriterAgentReturn]:
    """Run agent with exponential backoff retry logic.

    Args:
        agent: Configured writer agent
        state: Agent execution state
        prompt: System prompt

    Returns:
        Agent execution result with message history and usage metrics

    """
    max_attempts = 3
    result: RunResult[WriterAgentReturn] | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = agent.run_sync(prompt, deps=state)
            break
        except Exception as exc:  # Broad catch: retry on any error (network, API, timeout, etc.)
            if attempt == max_attempts:
                logger.exception("Writer agent failed after %s attempts", attempt)
                raise
            delay = attempt * 2
            logger.warning(
                "Writer agent attempt %s/%s failed: %s. Retrying in %ss...",
                attempt,
                max_attempts,
                exc,
                delay,
            )
            time.sleep(delay)

    # Type narrowing: result will always be set if we reach here (exception raised on final failure)
    assert result is not None, "Result should be set after successful retry or exception raised"
    return result


def _log_agent_completion(
    result: RunResult[WriterAgentReturn],
    saved_posts: list[str],
    saved_profiles: list[str],
    intercalated_log: list[JournalEntry],
    window_label: str,
) -> None:
    """Log agent completion metrics and results.

    Args:
        result: Agent execution result with message history and usage metrics
        saved_posts: List of created post IDs
        saved_profiles: List of updated profile IDs
        intercalated_log: Journal entries from execution
        window_label: Window identifier for logging

    """
    result_payload = getattr(result, "output", getattr(result, "data", result))
    usage = result.usage()

    logger.info(
        "Writer agent completed: period=%s posts=%d profiles=%d tokens=%d",
        window_label,
        len(saved_posts),
        len(saved_profiles),
        usage.total_tokens if usage else 0,
    )
    logger.info("Writer agent finished with summary: %s", getattr(result_payload, "summary", None))


def _record_agent_conversation(
    result: RunResult[WriterAgentReturn],
    context: WriterAgentContext,
) -> None:
    """Record agent conversation to file if configured.

    Args:
        result: Agent execution result with message history
        context: Runtime context with start_time and output paths

    """
    record_dir = os.environ.get("EGREGORA_LLM_RECORD_DIR")
    if not record_dir:
        return

    try:
        output_path = Path(record_dir).expanduser()
        output_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
        filename = output_path / f"writer-{context.start_time:%Y%m%d_%H%M%S}-{timestamp}.json"
        payload = ModelMessagesTypeAdapter.dump_json(result.all_messages())
        filename.write_bytes(payload)
        logger.info("Recorded writer agent conversation to %s", filename)
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        logger.warning("Failed to persist writer agent messages: %s", exc)


def write_posts_with_pydantic_agent(
    *,
    prompt: str,
    config: EgregoraConfig,
    context: WriterAgentContext,
    test_model: AgentModel | None = None,
) -> tuple[list[str], list[str]]:
    """Execute the writer flow using Pydantic-AI agent tooling."""
    logger.info("Running writer via Pydantic-AI backend")

    # Setup: Create agent, state, and window label
    agent, state, window_label = _setup_agent_and_state(config, context, test_model)

    # Validate: Check prompt fits in context window
    model_name = test_model if test_model is not None else config.models.writer
    _validate_prompt_fits(prompt, model_name, config, window_label)

    # Execute: Run agent and process results
    result = _run_agent_with_retries(agent, state, prompt)

    # Extract results from agent output
    saved_posts, saved_profiles = _extract_tool_results(result.all_messages())

    # Extract and save journal
    intercalated_log = _extract_intercalated_log(result.all_messages())
    _save_journal_to_file(intercalated_log, window_label, context.output_format)

    # Log comprehensive metrics
    _log_agent_completion(result, saved_posts, saved_profiles, intercalated_log, window_label)

    # Record conversation if configured
    _record_agent_conversation(result, context)

    return saved_posts, saved_profiles
