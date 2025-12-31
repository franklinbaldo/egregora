"""Profile post generation for authors.

Generates PROFILE posts (Egregora writing ABOUT authors) based on
their full message history in the current window.

## Append-Only Design
- **Each profile generation creates a NEW post** (never overwrites)
- Posts are saved to: `/posts/profiles/{author_uuid}/{slug}.md`
- Slugs are meaningful and include:
  - Date of analysis (YYYY-MM-DD)
  - Content focus (e.g., "technical-contributions", "photography-interests")
  - Author identifier (first 8 chars of UUID)
- Example path: `/posts/profiles/550e8400/2025-03-15-technical-contributions-550e8400.md`

## Design Principles
- One PROFILE post per author per window (if significant changes detected)
- LLM analyzes full message history
- LLM decides what to write about (interests, contributions, interactions)
- Flattering, appreciative tone
- Each analysis is preserved as a separate post (append-only)

## Integration with Profile Systems
This module generates DocumentType.PROFILE Documents that represent
Egregora's analysis of an author. These are distinct from the author's
self-service profile (managed in knowledge/profiles.py).

## Critical Metadata Requirement
**ALL** generated profile Documents MUST include:
- `subject`: The author's UUID (ensures proper routing to /posts/profiles/{uuid}/)
- `slug`: Unique, meaningful identifier for this profile post
- `authors`: Set to Egregora (the author OF the post)
- `date`: The window date for temporal ordering

The `subject` field is validated by `validate_profile_document()` before persistence
to prevent routing failures.
"""

import logging
from collections import defaultdict
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from egregora.common.text_utils import slugify
from egregora.constants import EGREGORA_NAME, EGREGORA_UUID
from egregora.data_primitives.document import Document, DocumentType
from egregora.orchestration.persistence import validate_profile_document

try:
    from egregora.agents.profile.history import get_profile_history_for_context
except ImportError:
    # Graceful fallback if history module not available
    from typing import Any

    def get_profile_history_for_context(*args: Any, **kwargs: Any) -> str:
        """Graceful fallback if profile history module not available."""
        return ""


logger = logging.getLogger(__name__)


def _generate_meaningful_slug(title: str, window_date: str, author_uuid: str) -> str:
    """Generate a meaningful, unique slug for a profile post.

    Creates append-only profile posts with semantic slugs that indicate:
    - The date of the analysis
    - The focus/aspect being analyzed (from title)
    - Author identifier for uniqueness

    Args:
        title: The profile post title (e.g., "John's Technical Contributions")
        window_date: The analysis date (YYYY-MM-DD)
        author_uuid: The author's UUID

    Returns:
        A meaningful slug like "2025-03-15-technical-contributions-john-550e"

    Examples:
        >>> _generate_meaningful_slug("Alice's Photography Interests", "2025-03-15", "alice-uuid-123")
        '2025-03-15-photography-interests-alice-ali'

    """
    # Extract meaningful part from title (remove author name prefix if present)
    title_parts = title.split(":", 1)
    if len(title_parts) > 1:
        # Title like "John Doe: Technical Contributions" -> use "Technical Contributions"
        aspect = title_parts[1].strip()
    else:
        aspect = title

    # Slugify the aspect
    aspect_slug = slugify(aspect)

    # Use short author identifier (first 8 chars of UUID)
    author_id = author_uuid[:8]

    # Combine into meaningful slug: date-aspect-author_id
    # Example: 2025-03-15-technical-contributions-550e8400
    return f"{window_date}-{aspect_slug}-{author_id}"


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
    profile_history: str = "",
) -> str:
    """Build prompt for LLM to generate profile content.

    Args:
        author_name: Name of author being profiled
        author_messages: All messages from this author in window
        window_date: Date of the window
        existing_profile: Current profile data (bio, interests) to check against
        profile_history: Compiled history of previous profile posts (from Jinja template)

    Returns:
        Prompt string for LLM

    """
    # Format messages for prompt
    messages_text = "\n".join(
        [f"[{msg.get('timestamp', 'unknown')}] {msg.get('text', '')}" for msg in author_messages]
    )

    def _normalize_interests(raw_interests: Any) -> list[str]:
        """Normalize interests to a list of strings for prompt construction."""
        if raw_interests is None:
            return []

        if isinstance(raw_interests, str):
            return [raw_interests]

        try:
            from collections.abc import Iterable

            if isinstance(raw_interests, Iterable):
                return list(raw_interests)
        except TypeError:
            # Non-iterables should be treated as empty
            return []

        return []

    existing_context = ""
    if existing_profile:
        bio = existing_profile.get("bio", "None")
        interests_list = _normalize_interests(existing_profile.get("interests"))
        interests = ", ".join(interests_list) or "None"
        existing_context = f"""
CURRENT PROFILE STATE:
Bio: {bio}
Interests: {interests}
"""

    history_context = ""
    if profile_history:
        history_context = f"""
PROFILE POST HISTORY:
{profile_history}

The above history shows your previous analyses of {author_name}.
Use this to:
1. Avoid repeating what you've already covered
2. Build on prior insights
3. Track evolution over time
4. Identify new aspects worth analyzing

"""

    return f"""You are Egregora, writing a profile post ABOUT {author_name}.

Analyze {author_name}'s contributions, interests, and interactions based on their message history below.

{existing_context}
{history_context}

DECISION REQUIRED:
Does the new message history below reveal SIGNIFICANT new information, contradict the current profile, or show a meaningful evolution in their stance/interests?
- If NO (just more of the same OR already covered in history): Set 'significant' to False.
- If YES: Set 'significant' to True and write a short (1-2 paragraph) appreciative profile update.

Update Content Guidelines (if significant):
- Highlight the NEW insights or changes.
- Build on (don't repeat) previous profile posts from history.
- Tone: Positive, flattering, appreciative.
- Format: Markdown with H1 title that includes the specific aspect (e.g., "Alice: Photography Techniques").

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
        except (OSError, yaml.YAMLError) as e:
            logger.warning("Failed to fetch existing profile for %s: %s", author_uuid, e)

    # Fetch profile history for context (append-only timeline of previous posts)
    profile_history = ""
    try:
        if hasattr(ctx, "output_dir"):
            from pathlib import Path

            profiles_dir = Path(ctx.output_dir) / "docs" / "posts" / "profiles"
            profile_history = get_profile_history_for_context(
                author_uuid, profiles_dir, max_posts=ctx.config.profile.history_window_size
            )
            logger.debug("Loaded profile history for %s (%d chars)", author_uuid, len(profile_history))
    except ImportError as e:
        logger.warning("Failed to load profile history for %s: %s", author_uuid, e)

    # Build prompt with history context
    prompt = _build_profile_prompt(
        author_name=author_name,
        author_messages=author_messages,
        window_date=author_messages[0].get("timestamp", "").split("T")[0] if author_messages else "",
        existing_profile=existing_profile,
        profile_history=profile_history,
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

            # Create meaningful, unique slug for append-only system
            # Each profile analysis gets its own file in the author's directory
            slug = _generate_meaningful_slug(title, window_date, author_uuid)

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

            # Validate that subject metadata is present
            validate_profile_document(profile)

            profiles.append(profile)
            logger.info("Generated profile update for %s: %s", author_name, title)

        except (ValueError, TypeError) as e:
            logger.exception(f"Failed to generate profile for {author_name}: {e}")
            continue

    return profiles
