"""Utility functions for setting up and configuring the Writer agent.

This module handles the dynamic construction of the writer agent,
including its capabilities, model, and tools, based on the application's
configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent, RunContext

from egregora.agents.types import WriterAgentReturn, WriterDeps
from egregora.agents.writer_helpers import (
    build_rag_context_for_prompt,
    load_profiles_context,
    register_writer_tools,
    validate_prompt_fits,
)
from egregora.llm.auth import get_google_api_key
from egregora.llm.exceptions import ApiKeyNotFoundError

if TYPE_CHECKING:
    from egregora.config.settings import EgregoraConfig


async def create_writer_model(
    config: EgregoraConfig,
    context: WriterDeps,
    prompt: str,
    test_model: Any | None = None,
) -> Any:
    """Create or configure the writer model."""
    if test_model is not None:
        return test_model

    model_name = config.models.writer
    if model_name.startswith("google-gla:"):
        try:
            get_google_api_key()  # Fail fast if key is missing
        except ApiKeyNotFoundError as e:
            msg = (
                "A Google model is configured, but no API key was found.\n"
                "Please set the GEMINI_API_key or GOOGLE_API_KEY environment variable.\n"
                "You can get a free key from Google AI Studio: https://aistudio.google.com/app/apikey"
            )
            raise ValueError(msg) from e

    # Directly instantiate the GoogleModel from pydantic-ai
    # This replaces the need for the `create_fallback_model` utility.
    if model_name.startswith("google-gla:"):
        model_name = model_name.replace("google-gla:", "")

    from pydantic_ai.models.google import GoogleModel

    model = GoogleModel(model_name=model_name)

    # Validate prompt fits (only check for real models)
    await validate_prompt_fits(prompt, config.models.writer, config, context.window_label)
    return model


def setup_writer_agent(
    model: Any,
    prompt: str,
    config: EgregoraConfig | None = None,
) -> Agent[WriterDeps, WriterAgentReturn]:
    """Initialize and configure the writer agent."""
    agent = Agent[WriterDeps, WriterAgentReturn](
        model=model,
        deps_type=WriterDeps,
        retries=3,
        system_prompt=prompt,
    )
    register_writer_tools(agent, config=config)

    # Dynamic System Prompts
    @agent.system_prompt
    def inject_rag_context(ctx: RunContext[WriterDeps]) -> str:
        if ctx.deps.resources.retrieval_config.enabled:
            table_markdown = ctx.deps.conversation_xml
            return build_rag_context_for_prompt(
                table_markdown,
                top_k=ctx.deps.resources.retrieval_config.top_k,
                cache=None,
            )
        return ""

    @agent.system_prompt
    def inject_profiles_context(ctx: RunContext[WriterDeps]) -> str:
        return load_profiles_context(ctx.deps.active_authors, ctx.deps.resources.output)

    return agent
