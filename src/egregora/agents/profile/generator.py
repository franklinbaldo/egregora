"""Profile post generation for authors.

Generates PROFILE posts (Egregora writing ABOUT authors) based on
their full message history in the current window.

Design:
- One PROFILE post per author per window
- LLM analyzes full message history
- LLM decides what to write about (interests, contributions, interactions)
- Flattering, appreciative tone
"""

import logging
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from egregora.constants import EGREGORA_NAME, EGREGORA_UUID
from egregora.data_primitives.document import Document, DocumentType

logger = logging.getLogger(__name__)


class ProfileUpdateDecision(BaseModel):
    """LLM decision on whether to update an author's profile."""

    significant: bool = Field(
        description="Does this window contradict or significantly add to the existing profile?"
    )
    content: str | None = Field(
        description="Markdown content of the profile update if significant, else None."
    )


def _build_profile_prompt(
    author_name: str,
    author_messages: list[dict[str, Any]],
    window_date: str,
    existing_profile: dict[str, Any] | None = None,
) -> str:
    """Build prompt for LLM to generate profile content.

    Args:
        author_name: Name of author being profiled
        author_messages: All messages from this author in window
        window_date: Date of the window
        existing_profile: Current profile data (bio, interests) to check against

    Returns:
        Prompt string for LLM

    """
    # Format messages for prompt
    messages_text = "\n".join(
        [f"[{msg.get('timestamp', 'unknown')}] {msg.get('text', '')}" for msg in author_messages]
    )

    existing_context = ""
    if existing_profile:
        bio = existing_profile.get("bio", "None")
        interests = ", ".join(existing_profile.get("interests", [])) or "None"
        existing_context = f"""
CURRENT PROFILE STATE:
Bio: {bio}
Interests: {interests}
"""

    return f"""You are Egregora, writing a profile post ABOUT {author_name}.

Analyze {author_name}'s contributions, interests, and interactions based on their message history below.

{existing_context}

DECISION REQUIRED:
Does the new message history below reveal SIGNIFICANT new information, contradict the current profile, or show a meaningful evolution in their stance/interests?
- If NO (just more of the same): Set 'significant' to False.
- If YES: Set 'significant' to True and write a short (1-2 paragraph) appreciative profile update.

Update Content Guidelines (if significant):
- Highlight the NEW insights or changes.
- Tone: Positive, flattering, appreciative.
- Format: Markdown with H1 title.

{author_name}'s New Messages ({len(author_messages)} total):

{messages_text}
"""



async def _generate_profile_content(
    ctx: Any,
    author_messages: list[dict[str, Any]],
    author_name: str,
    author_uuid: str,
) -> str | None:
    """Generate profile content using LLM with significance check.

    Args:
        ctx: Pipeline context with config
        author_messages: All messages from author
        author_name: Author's name
        author_uuid: Author's UUID

    Returns:
        Generated profile content (markdown) or None if not significant

    """
    # Fetch existing profile context
    existing_profile = None
    if hasattr(ctx.output_format, "get_author_profile"):
        try:
            existing_profile = ctx.output_format.get_author_profile(author_uuid)
        except Exception as e:
            logger.warning("Failed to fetch existing profile for %s: %s", author_uuid, e)

    # Build prompt
    prompt = _build_profile_prompt(
        author_name=author_name,
        author_messages=author_messages,
        window_date=author_messages[0].get("timestamp", "").split("T")[0] if author_messages else "",
        existing_profile=existing_profile,
    )

    # Call LLM
    decision = await _call_llm_decision(prompt, ctx)

    if not decision.significant:
        logger.info("Skipping profile update for %s (not significant)", author_name)
        return None

    return decision.content



async def _call_llm_decision(prompt: str, ctx: Any) -> ProfileUpdateDecision:
    """Call LLM with prompt and expect structured decision.

    Args:
        prompt: Prompt text
        ctx: Pipeline context with model config

    Returns:
        ProfileUpdateDecision object

    """
    # Get model from config
    model_name = ctx.config.models.writer

    # Create pydantic-ai agent with structured output
    agent = Agent(model_name, result_type=ProfileUpdateDecision)

    # Run agent
    result = await agent.run(prompt)

    return result.data


async def generate_profile_posts(
    ctx: Any, messages: list[dict[str, Any]], window_date: str
) -> list[Document]:
    """Generate PROFILE posts for all active authors in window.

    Generates profile posts only if significant updates are detected.

    Args:
        ctx: Pipeline context
        messages: All messages in window
        window_date: Window date (YYYY-MM-DD)

    Returns:
        List of PROFILE documents (one per author with significant updates)

    """
    # Group messages by author
    author_messages = defaultdict(list)
    author_names = {}

    for msg in messages:
        author_uuid = msg.get("author_uuid")
        if not author_uuid:
            continue

        author_messages[author_uuid].append(msg)
        author_names[author_uuid] = msg.get("author_name", "Unknown")

    # Generate one profile per author
    profiles = []

    for author_uuid, msgs in author_messages.items():
        author_name = author_names[author_uuid]

        logger.info("Analyzing profile significance for %s (%d messages)", author_name, len(msgs))

        try:
            # Generate content (returns None if not significant)
            content = await _generate_profile_content(
                ctx=ctx, author_messages=msgs, author_name=author_name, author_uuid=author_uuid
            )

            if not content:
                continue

            # Extract title from content (first H1)
            title_match = content.split("\n")[0]
            if title_match.startswith("# "):
                title = title_match[2:].strip()
            else:
                title = f"{author_name}: Profile Update"

            # Create slug
            slug = f"{window_date}-{author_uuid[:8]}-profile"

            # Create PROFILE document
            profile = Document(
                content=content,
                type=DocumentType.PROFILE,
                metadata={
                    "title": title,
                    "slug": slug,
                    "authors": [{"uuid": EGREGORA_UUID, "name": EGREGORA_NAME}],
                    "subject": author_uuid,
                    "date": window_date,
                },
            )

            profiles.append(profile)
            logger.info("Generated profile update for %s: %s", author_name, title)

        except Exception:
            logger.exception("Failed to generate profile for %s", author_name)
            continue

    return profiles
