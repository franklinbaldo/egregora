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

from pydantic_ai import Agent

from egregora.constants import EGREGORA_NAME, EGREGORA_UUID
from egregora.data_primitives.document import Document, DocumentType

logger = logging.getLogger(__name__)


def _build_profile_prompt(author_name: str, author_messages: list[dict[str, Any]], window_date: str) -> str:
    """Build prompt for LLM to generate profile content.

    Args:
        author_name: Name of author being profiled
        author_messages: All messages from this author in window
        window_date: Date of the window

    Returns:
        Prompt string for LLM

    """
    # Format messages for prompt
    messages_text = "\n".join(
        [f"[{msg.get('timestamp', 'unknown')}] {msg.get('text', '')}" for msg in author_messages]
    )

    prompt = f"""You are Egregora, writing a profile post ABOUT {author_name}.

Analyze {author_name}'s contributions, interests, and interactions based on their message history below.

Write a short (1-2 paragraph) appreciative profile highlighting:
- Key interests or themes in their messages
- Notable contributions or insights
- How they engage with others
- Any evolving patterns

Tone: Positive, flattering, appreciative
Format: Markdown with H1 title
Length: 1-2 paragraphs

{author_name}'s Messages ({len(author_messages)} total):

{messages_text}

Write the profile post now:"""

    return prompt


async def _generate_profile_content(
    ctx: Any, author_messages: list[dict[str, Any]], author_name: str, author_uuid: str
) -> str:
    """Generate profile content using LLM.

    Args:
        ctx: Pipeline context with config
        author_messages: All messages from author
        author_name: Author's name
        author_uuid: Author's UUID

    Returns:
        Generated profile content (markdown)

    """
    # Build prompt
    prompt = _build_profile_prompt(
        author_name=author_name,
        author_messages=author_messages,
        window_date=author_messages[0].get("timestamp", "").split("T")[0] if author_messages else "",
    )

    # Call LLM
    content = await _call_llm(prompt, ctx)

    return content


async def _call_llm(prompt: str, ctx: Any) -> str:
    """Call LLM with prompt.

    Args:
        prompt: Prompt text
        ctx: Pipeline context with model config

    Returns:
        LLM response

    """
    # Get model from config
    model_name = ctx.config.models.writer

    # Create pydantic-ai agent
    agent = Agent(model_name)

    # Run agent
    result = await agent.run(prompt)

    return result.data


async def generate_profile_posts(
    ctx: Any, messages: list[dict[str, Any]], window_date: str
) -> list[Document]:
    """Generate PROFILE posts for all active authors in window.

    Generates ONE profile post per author, analyzing their full
    message history. LLM decides what to write about.

    Args:
        ctx: Pipeline context
        messages: All messages in window
        window_date: Window date (YYYY-MM-DD)

    Returns:
        List of PROFILE documents (one per author)

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

        logger.info("Generating profile for %s (%d messages)", author_name, len(msgs))

        try:
            # Generate content
            content = await _generate_profile_content(
                ctx=ctx, author_messages=msgs, author_name=author_name, author_uuid=author_uuid
            )

            # Extract title from content (first H1)
            title_match = content.split("\n")[0]
            if title_match.startswith("# "):
                title = title_match[2:].strip()
            else:
                title = f"{author_name}: Profile"

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
            logger.info("Generated profile for %s: %s", author_name, title)

        except Exception:
            logger.exception("Failed to generate profile for %s", author_name)
            continue

    return profiles
