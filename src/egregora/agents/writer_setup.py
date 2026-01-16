"""Utility functions for setting up and configuring the Writer agent.

This module handles the dynamic construction of the writer agent,
including its capabilities, model, and tools, based on the application's
configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import infer_model
from pydantic_ai.settings import ModelSettings

from egregora.agents.types import WriterAgentReturn, WriterDeps
from egregora.agents.writer_helpers import (
    build_rag_context_for_prompt,
    load_profiles_context,
    register_writer_tools,
    validate_prompt_fits,
)
from egregora.config.settings import get_google_api_keys, get_openrouter_api_keys

if TYPE_CHECKING:
    from egregora.config.settings import EgregoraConfig


def create_writer_model(
    config: EgregoraConfig,
    context: WriterDeps,
    prompt: str,
    test_model: Any | None = None,
    api_key: str | None = None,
) -> Any:
    """Create or configure the writer model."""
    if test_model is not None:
        return test_model

    model_name = config.models.writer
    effective_key = api_key

    if model_name.startswith("google-gla:"):
        if not effective_key:
            google_keys = get_google_api_keys()
            if not google_keys:
                msg = (
                    "A Google model is configured, but no API key was found.\n"
                    "Please set the EGREGORA_GOOGLE_API_KEYS environment variable.\n"
                    "You can get a free key from Google AI Studio: https://aistudio.google.com/app/apikey"
                )
                raise ValueError(msg)
            effective_key = google_keys[0]

        model = infer_model(model_name)
        if hasattr(model, "api_key"):
            model.api_key = effective_key

    elif model_name.startswith("openrouter:"):
        if not effective_key:
            openrouter_keys = get_openrouter_api_keys()
            if not openrouter_keys:
                msg = (
                    "An OpenRouter model is configured, but no API key was found.\n"
                    "Please set the EGREGORA_OPENROUTER_API_KEYS environment variable.\n"
                    "You can get a key from OpenRouter: https://openrouter.ai/keys"
                )
                raise ValueError(msg)
            effective_key = openrouter_keys[0]

        model = infer_model(model_name)
        if hasattr(model, "api_key"):
            model.api_key = effective_key
    else:
        model = infer_model(model_name)

    # Validate prompt fits (only check for real models)
    validate_prompt_fits(prompt, config.models.writer, config, context.window_label, model_instance=model)
    return model


def setup_writer_agent(
    model: Any,
    prompt: str,
    config: EgregoraConfig | None = None,
    model_settings: ModelSettings | None = None,
) -> Agent[WriterDeps, WriterAgentReturn]:
    """Initialize and configure the writer agent."""
    agent = Agent[WriterDeps, WriterAgentReturn](
        model=model,
        deps_type=WriterDeps,
        retries=3,
        system_prompt=prompt,
        model_settings=model_settings,
        output_type=WriterAgentReturn,
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
