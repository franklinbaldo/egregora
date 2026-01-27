"""Enrichment-related functionalities for agents."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx
from pydantic_ai import Agent, BinaryContent

from egregora.agents.enricher import (
    EnrichmentOutput,
    load_file_as_binary_content,
)
from egregora.llm.api_keys import get_google_api_key
from egregora.ops.media import (
    detect_media_type,
)
from egregora.orchestration.cache import make_enrichment_cache_key
from egregora.orchestration.exceptions import CacheKeyNotFoundError
from egregora.resources.prompts import render_prompt

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from egregora.agents.avatar import AvatarContext
logger = logging.getLogger(__name__)


def enrich_avatar(
    avatar_path: Path,
    author_uuid: str,
    timestamp: datetime,
    context: AvatarContext,
) -> None:
    """Enrich avatar with LLM description using the media enrichment agent."""
    cache_key = make_enrichment_cache_key(kind="media", identifier=str(avatar_path))
    if context.cache:
        try:
            cached = context.cache.load(cache_key)
            if cached and cached.get("markdown"):
                logger.info("Using cached enrichment for avatar: %s", avatar_path.name)
                enrichment_path = avatar_path.with_suffix(avatar_path.suffix + ".md")
                enrichment_path.write_text(cached["markdown"], encoding="utf-8")
                return
        except CacheKeyNotFoundError:
            pass  # Not an error, just a cache miss
    try:
        binary_content = load_file_as_binary_content(avatar_path)
    except (OSError, ValueError) as exc:
        logger.warning("Failed to load avatar for enrichment: %s", exc)
        return
    media_type = detect_media_type(avatar_path)
    if not media_type:
        logger.warning("Could not detect media type for avatar: %s", avatar_path.name)
        return
    try:
        media_path = avatar_path.relative_to(context.docs_dir)
    except ValueError:
        media_path = avatar_path

    prompt = render_prompt(
        "enrichment.jinja",
        mode="media",
        prompts_dir=None,
        media_type=media_type,
        media_filename=avatar_path.name,
        media_path=str(media_path),
        original_message=f"Avatar set by {author_uuid}",
        sender_uuid=author_uuid,
        date=timestamp.strftime("%Y-%m-%d"),
        time=timestamp.strftime("%H:%M"),
    ).strip()

    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    try:
        model_name = context.vision_model
        provider = GoogleProvider(api_key=get_google_api_key())
        model = GoogleModel(
            model_name.removeprefix("google-gla:"),
            provider=provider,
        )
        agent = Agent(model=model, output_type=EnrichmentOutput)
        message_content: list[str | BinaryContent] = [
            prompt,
            binary_content,
        ]
        result = agent.run_sync(message_content)
        output = result.output
        markdown_content = output.markdown.strip()
        if not markdown_content:
            markdown_content = f"[No enrichment generated for avatar: {avatar_path.name}]"
        enrichment_path = avatar_path.with_suffix(avatar_path.suffix + ".md")
        enrichment_path.write_text(markdown_content, encoding="utf-8")
        logger.info("Saved avatar enrichment to: %s", enrichment_path)
        if context.cache:
            context.cache.store(cache_key, {"markdown": markdown_content, "type": "media"})
    except (httpx.HTTPError, OSError, ValueError, RuntimeError) as exc:
        logger.warning("Failed to enrich avatar %s: %s", avatar_path.name, exc)
