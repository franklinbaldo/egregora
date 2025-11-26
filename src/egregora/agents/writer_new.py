from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from llama_index.core.agent import AgentRunner
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.llms.gemini import Gemini

from egregora.agents.model_limits import validate_prompt_fits
from egregora.agents.tools.adapters import create_writer_tools
from egregora.agents.writer import JournalEntry, _save_journal_to_file

if TYPE_CHECKING:
    from egregora.agents.writer import WriterDeps
    from egregora.config.settings import EgregoraConfig

logger = logging.getLogger(__name__)


def _transform_llama_index_history_to_journal(
    history: list[ChatMessage],
) -> tuple[list[JournalEntry], list[str], list[str]]:
    """Convert LlamaIndex chat history to the standard journal format."""
    entries = []
    saved_posts = []
    saved_profiles = []

    for message in history:
        timestamp = datetime.now(UTC)  # LlamaIndex messages don't have timestamps

        if message.role == MessageRole.ASSISTANT:
            if message.content:
                entries.append(JournalEntry("journal", message.content, timestamp))
            if tool_calls := message.additional_kwargs.get("tool_calls"):
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    args_str = tool_call.function.arguments or "{}"
                    content = f"Tool: {tool_name}\nArguments:\n{args_str}"
                    entries.append(JournalEntry("tool_call", content, timestamp, tool_name))

        elif message.role == MessageRole.TOOL:
            tool_name = message.additional_kwargs.get("name", "unknown_tool")
            content = f"Result: {message.content}"
            entries.append(JournalEntry("tool_return", content, timestamp, tool_name))

            # Extract saved paths from tool results
            try:
                data = json.loads(message.content)
                if data.get("status") == "success" and "path" in data:
                    path = data["path"]
                    if tool_name == "write_post_tool":
                        saved_posts.append(path)
                    elif tool_name == "write_profile_tool":
                        saved_profiles.append(path)
            except (json.JSONDecodeError, TypeError):
                continue

    return entries, saved_posts, saved_profiles


def write_posts_with_llama_index(
    *,
    prompt: str,
    config: EgregoraConfig,
    context: WriterDeps,
    **_: Any,
) -> tuple[list[str], list[str]]:
    """Execute the writer flow using LlamaIndex agent tooling."""
    logger.info("Running writer via LlamaIndex backend")

    model_name = config.models.writer
    validate_prompt_fits(prompt, model_name, config, context.window_label)

    tools = create_writer_tools(context)
    llm = Gemini(model_name=model_name)
    memory = ChatMemoryBuffer.from_defaults(token_limit=llm.metadata.context_window - 2000)

    agent = AgentRunner.from_llm(llm=llm, tools=tools, memory=memory, verbose=True)
    agent.chat(prompt)

    history = memory.get_all()
    intercalated_log, saved_posts, saved_profiles = _transform_llama_index_history_to_journal(history)

    # Estimate token usage
    # This is a rough approximation; for precise numbers, a token counter is needed.
    total_tokens = sum(len(msg.content or "") for msg in history) // 4

    _save_journal_to_file(
        intercalated_log=intercalated_log,
        window_label=context.window_label,
        output_format=context.resources.output,
        posts_published=len(saved_posts),
        profiles_updated=len(saved_profiles),
        window_start=context.window_start,
        window_end=context.window_end,
        total_tokens=total_tokens,
    )

    logger.info(
        "Writer agent completed: period=%s posts=%d profiles=%d",
        context.window_label,
        len(saved_posts),
        len(saved_profiles),
    )

    return saved_posts, saved_profiles
