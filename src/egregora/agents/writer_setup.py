from __future__ import annotations

import logging
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
    load_profiles_context,
    register_writer_tools,
    validate_prompt_fits,
)
from egregora.rag import RAGQueryRequest
from egregora.utils.model_fallback import create_fallback_model

if TYPE_CHECKING:
    from egregora.config.settings import EgregoraConfig

logger = logging.getLogger(__name__)


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


def create_writer_model(
    config: EgregoraConfig,
    context: WriterDeps,
    prompt: str,
    test_model: Any | None = None,
) -> Any:
    """Create or configure the writer model."""
    if test_model is not None:
        return test_model

    model = create_fallback_model(config.models.writer, use_google_batch=False)
    # Validate prompt fits (only check for real models)
    validate_prompt_fits(prompt, config.models.writer, config, context.window_label)
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
        if ctx.deps.resources.rag_backend:
            # Reimplement RAG context building using injected backend
            table_markdown = ctx.deps.conversation_xml
            if not table_markdown or not table_markdown.strip():
                return ""

            query_text = table_markdown[:500]
            try:
                response = ctx.deps.resources.rag_backend.query(
                    RAGQueryRequest(text=query_text, top_k=ctx.deps.resources.retrieval_config.top_k)
                )
                if response and response.hits:
                    parts = [
                        "\n\n## Similar Posts (for context and inspiration):\n",
                        "These are similar posts from previous conversations that might provide useful context:\n\n",
                    ]
                    for idx, hit in enumerate(response.hits, 1):
                        similarity_pct = int(hit.score * 100)
                        parts.append(f"### Similar Post {idx} (similarity: {similarity_pct}%)\n")
                        parts.append(f"{hit.text[:500]}...\n\n")
                    return "".join(parts)
            except (ConnectionError, TimeoutError, RuntimeError) as exc:
                logger.warning("RAG backend unavailable for context injection: %s", exc)
            except ValueError as exc:
                logger.warning("Invalid RAG query for context injection: %s", exc)
            except Exception:
                # Fail silently for unexpected errors to avoid crashing writer
                pass
        return ""

    @agent.system_prompt
    def inject_profiles_context(ctx: RunContext[WriterDeps]) -> str:
        return load_profiles_context(ctx.deps.active_authors, ctx.deps.resources.output)

    return agent
