"""Pydantic-AI powered writer agent.

This module implements the writer workflow using Pydantic-AI.
It acts as the Composition Root for the agent, assembling core tools and
capabilities before executing the conversation through a ``pydantic_ai.Agent``.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, cast

from jinja2 import Environment, FileSystemLoader, select_autoescape
from jinja2.exceptions import TemplateError, TemplateNotFound
from pydantic_ai import AgentRunResult, UsageLimits
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ModelResponsePart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models import KnownModelName, Model
from pydantic_ai.settings import ModelSettings
from ratelimit import limits, sleep_and_retry  # type: ignore[import-untyped] # ratelimit missing stubs
from tenacity import Retrying

from egregora.agents.exceptions import AgentError
from egregora.agents.types import (
    PromptTooLargeError,
    WindowProcessingParams,
    WriterAgentReturn,
    WriterDeps,
    WriterResources,
)
from egregora.agents.writer_context import (
    WriterContext,
    WriterContextParams,
    WriterDepsParams,
    build_context_and_signature,
    check_writer_cache,
    index_new_content_in_rag,
    prepare_writer_dependencies,
)
from egregora.agents.writer_helpers import (
    process_tool_result,
)
from egregora.agents.writer_setup import (
    create_writer_model,
    setup_writer_agent,
)
from egregora.data_primitives.document import Document, DocumentType
from egregora.llm.api_keys import (
    get_google_api_keys,
    get_openrouter_api_keys,
)
from egregora.llm.retry import RETRY_IF, RETRY_STOP, RETRY_WAIT
from egregora.orchestration.cache import PipelineCache
from egregora.output_adapters.mkdocs.adapter import MkDocsAdapter
from egregora.output_adapters.mkdocs.site_generator import SiteGenerator
from egregora.resources.prompts import render_prompt

if TYPE_CHECKING:
    from egregora.config.settings import EgregoraConfig
    from egregora.data_primitives.document import OutputSink

logger = logging.getLogger(__name__)

# HTTP Status Codes
HTTP_STATUS_OK = 200
HTTP_STATUS_TOO_MANY_REQUESTS = 429
HTTP_STATUS_PAYMENT_REQUIRED = 402
HTTP_STATUS_BAD_REQUEST = 400
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_INTERNAL_SERVER_ERROR = 500


# Template names
WRITER_TEMPLATE_NAME = "writer.jinja"

# Centralized model rotation list
GEMINI_MODEL_PRIORITY = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3-flash-preview",
]
JOURNAL_TEMPLATE_NAME = "journal.md.jinja"
TEMPLATES_DIR_NAME = "templates"

# Fallback template identifier for cache signature
DEFAULT_TEMPLATE_SIGNATURE = "standard_writer_v1"

# Journal entry types
JOURNAL_TYPE_THINKING = "thinking"
JOURNAL_TYPE_TEXT = "journal"
JOURNAL_TYPE_TOOL_CALL = "tool_call"
JOURNAL_TYPE_TOOL_RETURN = "tool_return"

# Result keys
RESULT_KEY_POSTS = "posts"
RESULT_KEY_PROFILES = "profiles"

# Type aliases for improved type safety
MessageHistory = Sequence[ModelRequest | ModelResponse]
AgentModel = Model | KnownModelName

_WRITER_LOOP: asyncio.AbstractEventLoop | None = None
_KEY_ROTATION_INDEX: int = 0  # Global counter for proactive key rotation


# ============================================================================
# Agent Runners & Orchestration
# ============================================================================


def _extract_journal_content(messages: MessageHistory) -> str:
    """Extract journal content from agent message history."""
    journal_parts: list[str] = []
    for message in messages:
        if isinstance(message, ModelResponse):
            journal_parts.extend(part.content for part in message.parts if isinstance(part, TextPart))
    return "\n\n".join(journal_parts).strip()


@dataclass(frozen=True)
class JournalEntry:
    """Represents a single entry in the intercalated journal log."""

    entry_type: str  # "thinking", "journal", "tool_call", "tool_return"
    content: str
    timestamp: datetime | None = None
    tool_name: str | None = None


def _create_tool_call_entry(part: ToolCallPart, timestamp: datetime | None) -> JournalEntry:
    """Create a journal entry for a tool call part.

    Args:
        part: Tool call part from message
        timestamp: Message timestamp

    Returns:
        Journal entry for the tool call

    """
    args_str = json.dumps(part.args, indent=2) if hasattr(part, "args") else "{}"
    return JournalEntry(
        JOURNAL_TYPE_TOOL_CALL,
        f"Tool: {part.tool_name}\nArguments:\n{args_str}",
        timestamp,
        part.tool_name,
    )


def _process_response_part(part: ModelResponsePart, timestamp: datetime | None) -> JournalEntry | None:
    """Convert a message part to a journal entry."""
    if isinstance(part, ThinkingPart):
        return JournalEntry(JOURNAL_TYPE_THINKING, part.content, timestamp)
    if isinstance(part, TextPart):
        return JournalEntry(JOURNAL_TYPE_TEXT, part.content, timestamp)
    if isinstance(part, ToolCallPart):
        return _create_tool_call_entry(part, timestamp)
    # Note: ToolReturnPart is part of ModelRequest, not ModelResponse.
    # This check is technically unreachable for ModelResponsePart but kept for reference
    # or if the function is reused for ModelRequest parts in the future.
    if isinstance(part, ToolReturnPart):
        result_str = str(part.content) if hasattr(part, "content") else "No result"
        return JournalEntry(
            JOURNAL_TYPE_TOOL_RETURN,
            f"Result: {result_str}",
            timestamp,
            getattr(part, "tool_name", None),
        )
    return None


def _extract_intercalated_log(messages: MessageHistory) -> list[JournalEntry]:
    """Extract intercalated journal log preserving actual execution order."""
    entries: list[JournalEntry] = []

    for message in messages:
        timestamp = getattr(message, "timestamp", None)

        if isinstance(message, ModelResponse):
            entries.extend(
                filter(
                    None,
                    (_process_response_part(part, timestamp) for part in message.parts),
                )
            )

        elif isinstance(message, ModelRequest):
            # Help mypy with type narrowing in generator
            tool_parts: list[ToolCallPart] = [
                cast("ToolCallPart", p) for p in message.parts if isinstance(p, ToolCallPart)
            ]
            entries.extend(_create_tool_call_entry(part, timestamp) for part in tool_parts)

    return entries


def _get_writer_loop() -> asyncio.AbstractEventLoop:
    global _WRITER_LOOP
    if _WRITER_LOOP is None or _WRITER_LOOP.is_closed():
        _WRITER_LOOP = asyncio.new_event_loop()
    return _WRITER_LOOP


@dataclass
class WriterJournalEntryParams:
    """Parameters for saving a journal entry."""

    intercalated_log: list[JournalEntry]
    window_label: str
    output_sink: OutputSink
    posts_published: int
    profiles_updated: int
    window_start: datetime
    window_end: datetime
    total_tokens: int = 0


def _save_journal_to_file(params: WriterJournalEntryParams) -> str | None:
    """Save journal entry to markdown file.

    Raises:
        AgentError: If the journal template cannot be loaded, rendered, or written

    """
    intercalated_log = params.intercalated_log
    if not intercalated_log:
        return None

    templates_dir = Path(__file__).resolve().parents[1] / TEMPLATES_DIR_NAME
    now_utc = datetime.now(tz=UTC)
    window_start_iso = params.window_start.astimezone(UTC).isoformat()
    window_end_iso = params.window_end.astimezone(UTC).isoformat()
    journal_slug = now_utc.strftime("%Y-%m-%d-%H-%M-%S")

    try:
        # Security: Enable autoescape for markdown/jinja templates to prevent XSS in journals
        # This ensures that if the LLM outputs <script> tags, they are escaped in the rendered markdown
        env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "htm", "xml", "jinja", "md"]),
        )
        template = env.get_template(JOURNAL_TEMPLATE_NAME)
        journal_content = template.render(
            window_label=params.window_label,
            date=now_utc.strftime("%Y-%m-%d"),
            created=now_utc.isoformat(),
            posts_published=params.posts_published,
            profiles_updated=params.profiles_updated,
            entry_count=len(intercalated_log),
            intercalated_log=intercalated_log,
            window_start=window_start_iso,
            window_end=window_end_iso,
            total_tokens=params.total_tokens,
        )

        doc = Document(
            content=journal_content,
            type=DocumentType.JOURNAL,
            metadata={
                "title": f"Continuity Journal - {params.window_label}",
                "tags": ["journal"],
                "window_label": params.window_label,
                "window_start": window_start_iso,
                "window_end": window_end_iso,
                "date": now_utc.isoformat(),
                "created_at": now_utc.isoformat(),
                "slug": journal_slug,
                "nav_exclude": True,
                "hide": ["navigation"],
            },
            internal_metadata={
                "window_start": window_start_iso,
                "window_end": window_end_iso,
            },
            source_window=params.window_label,
        )
        params.output_sink.persist(doc)
        logger.info("Saved journal entry: %s", doc.document_id)
        return doc.document_id
    except (TemplateNotFound, TemplateError) as exc:
        msg = f"Journal template error for window {params.window_label}: {exc}"
        logger.exception(msg)
        raise AgentError(msg) from exc
    except (OSError, PermissionError) as exc:
        msg = f"File system error during journal creation for window {params.window_label}: {exc}"
        logger.exception(msg)
        raise AgentError(msg) from exc


def _process_single_tool_result(
    content: Any, tool_name: str | None, saved_posts: list[str], saved_profiles: list[str]
) -> None:
    """Process a single tool result and append to the appropriate list."""
    data = process_tool_result(content)
    if not data:
        logger.debug("Tool '%s' result could not be parsed as dict", tool_name)
        return

    status = data.get("status")
    path = data.get("path")

    if status not in ("success", "scheduled"):
        logger.debug("Tool '%s' result ignored due to status: %s", tool_name, status)
        return

    if not path:
        logger.debug("Tool '%s' result ignored due to missing path", tool_name)
        return

    if tool_name == "write_post_tool":
        logger.info("Found successfully saved post in tool results: %s", path)
        saved_posts.append(path)
    elif tool_name == "write_profile_tool":
        logger.info("Found successfully saved profile in tool results: %s", path)
        saved_profiles.append(path)
    else:
        logger.debug("Tool '%s' result processed but not a post/profile (status: %s)", tool_name, status)


def _extract_from_message(
    message: ModelRequest | ModelResponse, saved_posts: list[str], saved_profiles: list[str]
) -> None:
    """Extract tool results from a single message."""
    if hasattr(message, "parts"):
        for part in message.parts:
            if isinstance(part, ToolReturnPart):
                _process_single_tool_result(part.content, part.tool_name, saved_posts, saved_profiles)
    # Fallback for potentially older message structures or other types if Union expands
    elif hasattr(message, "kind") and message.kind == "tool-return":
        tool_name = getattr(message, "tool_name", None)
        _process_single_tool_result(getattr(message, "content", None), tool_name, saved_posts, saved_profiles)


def _extract_tool_results(messages: MessageHistory) -> tuple[list[str], list[str]]:
    """Extract saved post and profile document IDs from agent message history."""
    saved_posts: list[str] = []
    saved_profiles: list[str] = []

    logger.debug("Extracting tool results from %d agent messages", len(messages))
    for message in messages:
        _extract_from_message(message, saved_posts, saved_profiles)

    if saved_posts or saved_profiles:
        logger.info(
            "Agent Tool Results: %d posts, %d profiles extracted", len(saved_posts), len(saved_profiles)
        )
    else:
        logger.debug("No post/profile tool results extracted from agent history")

    return saved_posts, saved_profiles


# Type safe decorators for ratelimit
F = TypeVar("F", bound=Callable[..., Any])
_limits = cast("Callable[..., Callable[[F], F]]", limits)
_sleep_and_retry = cast("Callable[[F], F]", sleep_and_retry)


@_sleep_and_retry
@_limits(calls=100, period=60)
def write_posts_with_pydantic_agent(
    *,
    prompt: str,
    config: EgregoraConfig,
    context: WriterDeps,
    test_model: AgentModel | None = None,
    max_tokens_override: int | None = None,
    api_key_override: str | None = None,
) -> tuple[list[str], list[str]]:
    """Execute the writer flow using Pydantic-AI agent tooling."""
    logger.info("Running writer via Pydantic-AI backend")

    model = create_writer_model(config, context, prompt, test_model, api_key=api_key_override)
    model_settings: ModelSettings | None = None
    if config.models.writer.startswith("openrouter:"):
        model_settings = {"max_tokens": max_tokens_override or 1024}
    agent = setup_writer_agent(model, prompt, config=config, model_settings=model_settings)

    if context.resources.quota:
        context.resources.quota.reserve(1)

    logger.info(
        "Starting writer agent: period=%s messages=%d xml_chars=%d",
        context.window_label,
        len(context.messages),
        len(context.conversation_xml),
    )

    if not context.messages:
        logger.warning("Writer agent called with 0 messages for window %s", context.window_label)
        return [], []

    # Log the first 500 characters of the XML for debugging
    logger.debug("Conversation XML snippet (first 500 chars): %s", context.conversation_xml[:500])

    # Define usage limits
    usage_limits = UsageLimits(
        request_limit=15,  # Reasonable limit for tool loops
    )

    result = None

    # Use tenacity for retries
    def _run_agent_sync(loop: asyncio.AbstractEventLoop) -> AgentRunResult[WriterAgentReturn]:
        async def _run_async() -> AgentRunResult[WriterAgentReturn]:
            return await agent.run(
                "Analyze the conversation context provided and write posts/profiles as needed.",
                deps=context,
                usage_limits=usage_limits,
            )

        if loop.is_running():
            msg = "Writer loop already running; cannot run synchronously."
            raise RuntimeError(msg)
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run_async())
        finally:
            asyncio.set_event_loop(None)

    loop = _get_writer_loop()
    try:
        for attempt in Retrying(stop=RETRY_STOP, wait=RETRY_WAIT, retry=RETRY_IF, reraise=True):
            with attempt:
                # Execute model directly without tools
                result = _run_agent_sync(loop)
    except Exception as e:
        logger.exception("Error during agent run: %s", e)
        raise
    finally:
        loop.close()

    if not result:
        msg = "Agent failed to return a result"
        raise RuntimeError(msg)

    # Log total tool calls made
    tool_calls = [
        p for m in result.all_messages() if hasattr(m, "parts") for p in m.parts if hasattr(p, "tool_name")
    ]
    logger.info("Agent run complete. Total tool calls attempt: %d", len(tool_calls))
    for tc in tool_calls:
        logger.info("  - Called tool: %s", getattr(tc, "tool_name", "unknown"))

    usage = result.usage()
    if context.resources.usage:
        context.resources.usage.record(usage)
    messages = result.all_messages()
    saved_posts, saved_profiles = _extract_tool_results(messages)
    if not saved_posts and not saved_profiles:
        has_tool_calls = any(
            isinstance(part, ToolCallPart) for message in messages for part in getattr(message, "parts", [])
        )
        if not has_tool_calls:
            msg = "Writer response did not include any tool calls."
            raise AgentError(msg)
    intercalated_log = _extract_intercalated_log(messages)
    # TODO: [Taskmaster] Refactor complex journal fallback logic
    if not intercalated_log:
        fallback_content = _extract_journal_content(result.all_messages())
        if fallback_content:
            # Strip frontmatter if present (to avoid double frontmatter)
            if fallback_content.strip().startswith("---"):
                try:
                    _, _, body = fallback_content.strip().split("---", 2)
                    fallback_content = body.strip()
                except ValueError:
                    pass  # Failed to split, keep original

            intercalated_log = [JournalEntry("journal", fallback_content, datetime.now(tz=UTC))]
        else:
            intercalated_log = [
                JournalEntry(
                    "journal",
                    "Writer agent completed without emitting a detailed reasoning trace.",
                    datetime.now(tz=UTC),
                )
            ]
    _save_journal_to_file(
        WriterJournalEntryParams(
            intercalated_log=intercalated_log,
            window_label=context.window_label,
            output_sink=context.resources.output,
            posts_published=len(saved_posts),
            profiles_updated=len(saved_profiles),
            window_start=context.window_start,
            window_end=context.window_end,
            total_tokens=result.usage().total_tokens if result.usage() else 0,
        )
    )

    logger.info(
        "Writer agent completed: period=%s posts=%d profiles=%d tokens=%d",
        context.window_label,
        len(saved_posts),
        len(saved_profiles),
        result.usage().total_tokens if result.usage() else 0,
    )

    return saved_posts, saved_profiles


def _render_writer_prompt(
    context: WriterContext,
    prompts_dir: Path | None,
) -> str:
    """Render the final writer prompt text."""
    return render_prompt(
        "writer.jinja",
        prompts_dir=prompts_dir,
        **context.template_context,
    )


def _get_openrouter_free_models() -> list[str]:
    """Fetch free models from OpenRouter API as a final fallback."""
    import httpx

    try:
        response = httpx.get("https://openrouter.ai/api/v1/models", params={"free": "true"}, timeout=10.0)
        if response.status_code == HTTP_STATUS_OK:
            data = response.json()
            models = [f"openrouter:{m['id']}" for m in data.get("data", [])]
            if models:
                logger.info("[WriterRotation] Fetched %d free models from OpenRouter", len(models))
                return models
    except httpx.HTTPError as exc:
        logger.warning("[WriterRotation] Failed to fetch OpenRouter free models: %s", exc)
    return []


def _iter_writer_models(config: EgregoraConfig) -> list[str]:
    """Iterate through prioritized models, preserving provider choice."""
    model_name = config.models.writer
    all_candidates = [model_name]

    if model_name.startswith("google-gla:"):
        all_candidates.extend([f"google-gla:{name}" for name in GEMINI_MODEL_PRIORITY])
    elif model_name.startswith("openrouter:"):
        all_candidates.extend([f"openrouter:google/{name}" for name in GEMINI_MODEL_PRIORITY])

    if model_name.startswith("openrouter:") or config.enrichment.model_rotation_enabled:
        all_candidates.extend(_get_openrouter_free_models())

    seen: set[str] = set()
    unique_candidates: list[str] = []
    for m in all_candidates:
        if m not in seen:
            seen.add(m)
            unique_candidates.append(m)
    return unique_candidates


def _iter_provider_keys(model_name: str) -> list[str]:
    if model_name.startswith("google-gla:"):
        return get_google_api_keys()
    if model_name.startswith("openrouter:"):
        return get_openrouter_api_keys()
    return [None]


def _override_text_models(config: EgregoraConfig, model_name: str) -> EgregoraConfig:
    return config.model_copy(
        deep=True,
        update={
            "models": config.models.model_copy(
                update={
                    "writer": model_name,
                    "enricher": model_name,
                    "enricher_vision": model_name,
                    "ranking": model_name,
                    "editor": model_name,
                    "reader": model_name,
                }
            )
        },
    )


def _should_cycle(exc: Exception) -> bool:
    """Determine if the agent should cycle to the next model/key."""
    if isinstance(exc, (UsageLimitExceeded, AgentError)) and "tool calls" in str(exc).lower():
        return True
    if isinstance(exc, UsageLimitExceeded):
        return True

    if isinstance(exc, ModelHTTPError):
        if exc.status_code == HTTP_STATUS_TOO_MANY_REQUESTS:
            return True
        if exc.status_code == HTTP_STATUS_PAYMENT_REQUIRED:
            return True
        if exc.status_code in (HTTP_STATUS_BAD_REQUEST, HTTP_STATUS_NOT_FOUND):
            msg = str(exc).lower()
            if "not found" in msg or "not supported for generatecontent" in msg:
                return True
            if "not a valid model id" in msg:
                return True
            if (
                "response modalities" in msg
                or "accepts the following combination of response modalities" in msg
            ):
                return True
            if "function calling is not enabled" in msg:
                return True

        # Always cycle on severe server errors
        if exc.status_code >= 500:
            return True

    if isinstance(exc, RuntimeError):
        msg = str(exc).lower()
        if "event loop is closed" in msg:
            return True

    return False


def _get_openrouter_affordable_tokens(exc: ModelHTTPError) -> int | None:
    """Extract affordable token limit from OpenRouter error message."""
    if exc.status_code != HTTP_STATUS_PAYMENT_REQUIRED:
        return None

    message = ""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        message = str(body.get("message", ""))
    if not message:
        message = str(exc)

    match = re.search(r"can only afford (\d+)", message)
    if match:
        return int(match.group(1))
    return None


def _execute_writer_with_error_handling(
    prompt: str,
    config: EgregoraConfig,
    deps: WriterDeps,
) -> tuple[list[str], list[str]]:
    global _KEY_ROTATION_INDEX, _WRITER_LOOP
    last_exc: Exception | None = None
    openrouter_max_tokens: int | None = None
    model_names = _iter_writer_models(config)

    for model_idx, model_name in enumerate(model_names):
        # Create a new event loop for each persona to prevent state leakage
        if _WRITER_LOOP is not None and not _WRITER_LOOP.is_closed():
            _WRITER_LOOP.close()
        _WRITER_LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_WRITER_LOOP)

        provider_keys = _iter_provider_keys(model_name)
        num_keys = len(provider_keys)
        key_idx = _KEY_ROTATION_INDEX % num_keys if num_keys > 0 else 0

        logger.info(
            "[WriterRotation] Trying model %s (%d/%d), starting key index %d",
            model_name,
            model_idx + 1,
            len(model_names),
            key_idx,
        )

        for attempt in range(num_keys or 1):
            current_key_idx = (key_idx + attempt) % num_keys if num_keys > 0 else 0
            key = provider_keys[current_key_idx] if num_keys > 0 else None
            masked_key = (key[:8] + "...") if key else "default"
            logger.info(
                "[WriterRotation] Attempt %d/%d: model=%s key=%s",
                attempt + 1,
                num_keys or 1,
                model_name,
                masked_key,
            )

            try:
                result = write_posts_with_pydantic_agent(
                    prompt=prompt,
                    config=_override_text_models(config, model_name),
                    context=deps,
                    max_tokens_override=openrouter_max_tokens,
                    api_key_override=key,
                )
                _KEY_ROTATION_INDEX = (current_key_idx + 1) % num_keys if num_keys > 0 else 0
                return result
            except PromptTooLargeError:
                raise
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "[WriterRotation] Attempt failed: model=%s, key=%s, error=%s",
                    model_name,
                    masked_key,
                    str(exc)[:200],
                )
                if _should_cycle(exc):
                    if (
                        isinstance(exc, ModelHTTPError)
                        and "openrouter" in model_name
                        and (affordable := _get_openrouter_affordable_tokens(exc))
                        and (openrouter_max_tokens is None or affordable < openrouter_max_tokens)
                    ):
                        openrouter_max_tokens = affordable
                        logger.warning(
                            "[WriterRotation] Retrying with affordable token limit: %d", affordable
                        )
                        continue
                    logger.warning("[WriterRotation] Cycling to next key/model.")
                    continue

                msg = f"Non-recoverable writer agent failure for {deps.window_label}"
                raise RuntimeError(msg) from exc
        _KEY_ROTATION_INDEX = 0

    msg = f"Writer agent exhausted ALL models and keys for {deps.window_label}"
    raise RuntimeError(msg) from last_exc


@dataclass
class WriterFinalizationParams:
    """Parameters for finalizing writer results."""

    saved_posts: list[str]
    saved_profiles: list[str]
    resources: WriterResources
    deps: WriterDeps
    cache: PipelineCache
    signature: str


def _finalize_writer_results(params: WriterFinalizationParams) -> dict[str, list[str]]:
    """Finalize window results: output, RAG indexing, and caching.

    Returns:
        Result payload dict with 'posts' and 'profiles' keys

    """
    _regenerate_site_indices(params.resources.output)

    # Index newly created content in RAG
    index_new_content_in_rag(params.resources, params.saved_posts, params.saved_profiles)

    # Update L3 cache
    result_payload = {RESULT_KEY_POSTS: params.saved_posts, RESULT_KEY_PROFILES: params.saved_profiles}
    params.cache.writer.set(params.signature, result_payload)

    return result_payload


# TODO: [Taskmaster] Refactor complex `write_posts_for_window` function
def write_posts_for_window(params: WindowProcessingParams) -> dict[str, list[str]]:
    """Public entry point for the writer agent."""
    if params.smoke_test:
        logger.info("Smoke test mode: skipping writer agent.")
        return {RESULT_KEY_POSTS: [], RESULT_KEY_PROFILES: []}

    # We check if messages list is empty
    if not params.messages:
        logger.warning("write_posts_for_window called with 0 messages for window %s", params.window_label)
        return {RESULT_KEY_POSTS: [], RESULT_KEY_PROFILES: []}

    # NEW: Trace message count
    logger.info("Writer agent received %d messages for processing", len(params.messages))

    # 1. Prepare dependencies (partial, will update with context later)
    resources = params.resources
    if params.run_id and resources.run_id is None:
        # Create new resources with run_id
        resources = dataclasses.replace(resources, run_id=params.run_id)

    # 2. Build context and calculate signature
    # We need to build context first to get XML for signature
    writer_context, signature = build_context_and_signature(
        WriterContextParams(
            table=params.table,
            resources=resources,
            cache=params.cache,
            config=params.config,
            window_label=f"{params.window_start:%Y-%m-%d %H:%M} to {params.window_end:%H:%M}",
            adapter_content_summary=params.adapter_content_summary,
            adapter_generation_instructions=params.adapter_generation_instructions,
        ),
        resources.prompts_dir,
    )

    # 3. Check L3 cache
    cached_result = check_writer_cache(
        params.cache,
        signature,
        f"{params.window_start:%Y-%m-%d %H:%M} to {params.window_end:%H:%M}",
        resources.usage,
    )
    if cached_result:
        # TODO: [Taskmaster] Refactor brittle cache validation logic
        # Validate cached posts still exist on disk (they may be missing if output dir is fresh)
        cached_posts = cached_result.get(RESULT_KEY_POSTS, [])
        if cached_posts:
            # Check if at least one post file exists
            posts_exist = True
            if hasattr(resources.output, "posts_dir"):
                posts_exist = any(
                    list(resources.output.posts_dir.glob(f"*{slug}*.md"))
                    for slug in cached_posts[:1]  # Check first post only for speed
                )

            if not posts_exist:
                logger.warning(
                    "⚠️ Cached posts not found on disk, regenerating for window %s",
                    f"{params.window_start:%Y-%m-%d %H:%M} to {params.window_end:%H:%M}",
                )
                # Invalidate this cache entry
                params.cache.writer.delete(signature)
            else:
                _regenerate_site_indices(resources.output)
                return cached_result
        else:
            return cached_result

    logger.info("Using Pydantic AI backend for writer")

    # 4. Create Deps with the generated context
    deps = prepare_writer_dependencies(
        WriterDepsParams(
            window_start=params.window_start,
            window_end=params.window_end,
            resources=resources,
            model_name=params.config.models.writer,
            messages=params.messages,
            table=params.table,
            config=params.config,
            conversation_xml=writer_context.conversation_xml,
            active_authors=writer_context.active_authors,
            adapter_content_summary=params.adapter_content_summary,
            adapter_generation_instructions=params.adapter_generation_instructions,
        )
    )

    # Trace final deps message count
    logger.info("WriterDeps initialized with %d messages", len(deps.messages))

    # 5. Render prompt and execute agent
    # NOTE: _render_writer_prompt uses writer_context, which we stripped RAG/Profiles from.
    # The Jinja template must be robust to missing/empty rag_context/profiles_context
    # OR we need to trust the dynamic system prompts to fill them in.
    # The current Jinja template (viewed earlier) has placeholders:
    # {% if profiles_context %}{{ profiles_context }}{% endif %}
    # If they are empty strings, they won't render in the user prompt, which is what we want,
    # because they will be injected by system prompts.

    prompt = _render_writer_prompt(writer_context, deps.resources.prompts_dir)

    # Execute writer with error handling (removed economic mode - never worked)
    saved_posts, saved_profiles = _execute_writer_with_error_handling(prompt, params.config, deps)

    # 6. Finalize results (output, RAG indexing, caching)
    return _finalize_writer_results(
        WriterFinalizationParams(
            saved_posts=saved_posts,
            saved_profiles=saved_profiles,
            resources=resources,
            deps=deps,
            cache=params.cache,
            signature=signature,
        )
    )


def _regenerate_site_indices(adapter: OutputSink) -> None:
    """Helper to regenerate all site indices using SiteGenerator."""
    if not isinstance(adapter, MkDocsAdapter):
        logger.debug("Output format is not MkDocs, skipping site generation.")
        return

    if not adapter.site_root:
        logger.warning("Site root is not set, skipping site generation.")
        return

    # Load config to get reader database path
    from egregora.config import load_egregora_config

    try:
        config = load_egregora_config(adapter.site_root)
        db_path = adapter.site_root / config.reader.database_path
    except Exception as e:
        logger.debug("Could not load reader database path: %s", e)
        db_path = None

    site_generator = SiteGenerator(
        site_root=adapter.site_root,
        docs_dir=adapter.docs_dir,
        posts_dir=adapter.posts_dir,
        profiles_dir=adapter.profiles_dir,
        media_dir=adapter.media_dir,
        journal_dir=adapter.journal_dir,
        url_convention=adapter.url_convention,
        url_context=adapter.url_context,
        db_path=db_path,
    )
    site_generator.regenerate_main_index()
    site_generator.regenerate_profiles_index()
    site_generator.regenerate_media_index()
    site_generator.regenerate_tags_page()
    site_generator.regenerate_feeds_page()
    logger.info("Successfully regenerated site indices.")
<<<<<<< HEAD
=======


def load_format_instructions(site_root: Path | None, *, registry: OutputSinkRegistry | None = None) -> str:
    """Load output format instructions for the writer agent."""
    registry = registry or create_default_output_registry()

    if site_root:
        detected_format = registry.detect_format(site_root)
        if detected_format:
            return detected_format.get_format_instructions()

    try:
        default_format = registry.get_format("mkdocs")
        return default_format.get_format_instructions()
    except KeyError:
        return ""


def get_top_authors(table: Table, limit: int = 20) -> list[str]:
    """Get top N active authors by message count.

    Deprecated: Use Message DTOs filtering instead.
    """
    author_counts = (
        table.filter(~table.author_uuid.cast("string").isin(["system", "egregora"]))
        .filter(table.author_uuid.notnull())
        .filter(table.author_uuid.cast("string") != "")
        .group_by("author_uuid")
        .aggregate(count=table.author_uuid.count())
        .order_by(ibis.desc("count"))
        .limit(limit)
    )
    if author_counts.count().execute() == 0:
        return []
    return cast("list[str]", author_counts.author_uuid.cast("string").execute().tolist())
>>>>>>> origin/pr/2676
