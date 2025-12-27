"""Utility functions for setting up and configuring the Writer agent.

This module handles the dynamic construction of the writer agent,
including its capabilities, model, and tools, based on the application's
configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent, RunContext

from egregora.agents.banner.agent import is_banner_generation_available
from egregora.agents.capabilities import (
    AgentCapability,
    BackgroundBannerCapability,
    BannerCapability,
    RagCapability,
)
from egregora.agents.types import WriterAgentReturn, WriterDeps
from egregora.agents.writer_helpers import (
    build_rag_context_for_prompt,
    load_profiles_context,
    register_writer_tools,
    validate_prompt_fits,
)
from egregora.config.settings import google_api_key_status

if TYPE_CHECKING:
    from egregora.config.settings import EgregoraConfig


def configure_writer_capabilities(
    config: EgregoraConfig,
    context: WriterDeps,
) -> list[AgentCapability]:
    """Configure capabilities for the writer agent."""
    capabilities: list[AgentCapability] = []
    if config.rag.enabled:
        capabilities.append(RagCapability())

    if is_banner_generation_available():
        if context.resources.task_store and context.resources.run_id:
            capabilities.append(BackgroundBannerCapability(context.resources.run_id))
        else:
            capabilities.append(BannerCapability())

    return capabilities


async def create_writer_model(
    config: EgregoraConfig,
    context: WriterDeps,
    prompt: str,
    test_model: Any | None = None,
) -> Any:
    """Create or configure the writer model."""
    if test_model is not None:
        return test_model

    # Fail fast if a Google model is requested without an API key
    if config.models.writer.startswith("google-gla:") and not google_api_key_status():
        msg = (
            "A Google model is configured, but no API key was found.\n"
            "Please set the GEMINI_API_key or GOOGLE_API_KEY environment variable.\n"
            "You can get a free key from Google AI Studio: https://aistudio.google.com/app/apikey"
        )
        raise ValueError(msg)

    # Infer model from config string (e.g., "google-gla:gemini-2.0-flash")
    model = infer_model(config.models.writer)
    # Validate prompt fits (only check for real models)
    await validate_prompt_fits(prompt, config.models.writer, config, context.window_label)
    return model


def setup_writer_agent(
    model: Any,
    prompt: str,
    capabilities: list[AgentCapability],
) -> Agent[WriterDeps, WriterAgentReturn]:
    """Initialize and configure the writer agent."""
    agent = Agent[WriterDeps, WriterAgentReturn](
        model=model,
        deps_type=WriterDeps,
        retries=3,
        system_prompt=prompt,
    )
    register_writer_tools(agent, capabilities=capabilities)

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
