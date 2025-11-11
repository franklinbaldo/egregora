"""Pydantic AI-powered ranking agent using three-turn conversation protocol.

This module migrates the ranking agent from google.genai to Pydantic AI,
maintaining the same three-turn protocol:
1. Choose winner (A or B)
2. Comment on Post A (stars + comment)
3. Comment on Post B (stars + comment)

MODERN (Phase 1): Deps are frozen/immutable, no mutation in tools.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent, RunContext
from rich.console import Console

from egregora.agents.ranking.elo import calculate_elo_update
from egregora.agents.ranking.store import RankingStore
from egregora.config import resolve_site_paths
from egregora.config.schema import DEFAULT_MODEL
from egregora.prompt_templates import RankingComparisonPromptTemplate, RankingSystemPromptTemplate
from egregora.utils.logfire_config import logfire_span

console = Console()
logger = logging.getLogger(__name__)
FRONTMATTER_PARTS = 3
MAX_COMMENT_LENGTH = 250
COMMENT_TRUNCATE_SUFFIX = "..."
MIN_STARS = 1
MAX_STARS = 5


class WinnerChoice(BaseModel):
    """Result of choosing a winner."""

    winner: str = Field(description="'A' or 'B'", pattern="^[AB]$")


class PostComment(BaseModel):
    """Comment and rating for a post."""

    comment: str = Field(description="Markdown comment, max 250 chars")
    stars: int = Field(description="Star rating 1-5", ge=MIN_STARS, le=MAX_STARS)


class RankingResult(BaseModel):
    """Final result from ranking agent after all three turns."""

    winner: str = Field(description="'A' or 'B'")
    comment_a: str
    stars_a: int = Field(ge=MIN_STARS, le=MAX_STARS)
    comment_b: str
    stars_b: int = Field(ge=MIN_STARS, le=MAX_STARS)


class RankingAgentState(BaseModel):
    """Immutable dependencies passed to ranking agent tools.

    MODERN (Phase 1): This is now frozen to prevent mutation in tools.
    Results are extracted from the agent's message history instead of being
    tracked via mutation.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)
    post_a_id: str
    post_b_id: str
    content_a: str
    content_b: str
    profile: dict[str, Any]
    existing_comments_a: str | None
    existing_comments_b: str | None
    store: RankingStore
    site_dir: Path


class ComparisonData(BaseModel):
    """Data for a single comparison between two posts."""

    profile_id: str
    post_a: str
    post_b: str
    winner: str
    comment_a: str
    stars_a: int
    comment_b: str
    stars_b: int


class ComparisonConfig(BaseModel):
    """Configuration for running a comparison."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    site_dir: Path
    post_a_id: str
    post_b_id: str
    profile_path: Path
    api_key: str
    model: str = DEFAULT_MODEL
    agent_model: object | None = None
    prompts_dir: Path | None = None  # Custom prompts directory (e.g., site_root/.egregora/prompts)


def _parse_message_content(content: Any) -> dict[str, Any] | None:
    """Parse message content into a dictionary.

    Args:
        content: Message content (string, Pydantic model, or dict)

    Returns:
        Parsed dictionary or None if parsing fails

    """
    if isinstance(content, str):
        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return None
    if hasattr(content, "model_dump"):
        return content.model_dump()
    if hasattr(content, "__dict__"):
        return vars(content)
    if isinstance(content, dict):
        return content
    return None


def _is_winner_data(data: dict[str, Any]) -> bool:
    """Check if data contains winner choice."""
    return "winner" in data and "comment" not in data and "stars" not in data


def _is_comment_data(data: dict[str, Any]) -> bool:
    """Check if data contains post comment."""
    return "comment" in data and "stars" in data


class _CommentState:
    """Mutable state for tracking comments during parsing."""

    def __init__(self) -> None:
        """Initialize empty comment state."""
        self.comment_a: str | None = None
        self.stars_a: int | None = None
        self.comment_b: str | None = None
        self.stars_b: int | None = None

    def assign_comment(self, data: dict[str, Any], tool_name: str) -> None:
        """Assign comment data to the appropriate post (A or B).

        Args:
            data: Parsed comment data
            tool_name: Name of the tool that produced the data

        """
        comment = data["comment"]
        stars = data["stars"]

        if "post_a" in tool_name.lower() and self.comment_a is None:
            self.comment_a = comment
            self.stars_a = stars
        elif "post_b" in tool_name.lower() and self.comment_b is None:
            self.comment_b = comment
            self.stars_b = stars
        elif self.comment_a is None:
            self.comment_a = comment
            self.stars_a = stars
        elif self.comment_b is None:
            self.comment_b = comment
            self.stars_b = stars


def _extract_ranking_results(messages: Any) -> RankingResult:
    """Extract ranking results from agent message history.

    Parses the agent's tool call results to find WinnerChoice and PostComment returns.

    Args:
        messages: Agent message history

    Returns:
        RankingResult with all three tool results

    Raises:
        ValueError: If any required tool result is missing

    """
    winner: str | None = None
    state = _CommentState()

    try:
        for message in messages:
            if not (hasattr(message, "kind") and message.kind == "tool-return"):
                continue

            data = _parse_message_content(message.content)
            if not isinstance(data, dict):
                continue

            if _is_winner_data(data):
                winner = data["winner"]
            elif _is_comment_data(data):
                tool_name = getattr(message, "tool_name", None) or ""
                state.assign_comment(data, tool_name)
    except (AttributeError, TypeError) as e:
        logger.debug("Could not parse tool results: %s", e)

    # Validate all results were found
    if winner is None:
        msg = "Agent did not choose a winner"
        raise ValueError(msg)
    if state.comment_a is None or state.stars_a is None:
        msg = "Agent did not comment on Post A"
        raise ValueError(msg)
    if state.comment_b is None or state.stars_b is None:
        msg = "Agent did not comment on Post B"
        raise ValueError(msg)

    return RankingResult(
        winner=winner,
        comment_a=state.comment_a,
        stars_a=state.stars_a,
        comment_b=state.comment_b,
        stars_b=state.stars_b,
    )


def load_post_content(post_path: Path) -> str:
    """Load markdown content from a blog post, excluding front matter."""
    content = post_path.read_text()
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= FRONTMATTER_PARTS:
            return parts[2].strip()
    return content.strip()


def _extract_alias_from_lines(lines: list[str], start_idx: int) -> str | None:
    """Extract alias from Display Preferences section.

    Args:
        lines: Content lines
        start_idx: Index of "## Display Preferences" line

    Returns:
        Alias string or None

    """
    for j in range(start_idx + 1, min(start_idx + 5, len(lines))):
        if lines[j].strip().startswith("- Alias:"):
            return lines[j].split("- Alias:", 1)[1].strip()
    return None


def _extract_bio_from_lines(lines: list[str], start_idx: int) -> str | None:
    """Extract bio from Bio section.

    Args:
        lines: Content lines
        start_idx: Index of "## Bio" line

    Returns:
        Bio string or None

    """
    bio_lines = []
    for j in range(start_idx + 2, len(lines)):
        if lines[j].strip().startswith("##"):
            break
        bio_lines.append(lines[j])
    bio_text = "\n".join(bio_lines).strip()
    return bio_text if bio_text else None


def load_profile(profile_path: Path) -> dict[str, Any]:
    """Load author profile metadata."""
    content = profile_path.read_text()
    lines = content.split("\n")
    profile: dict[str, Any] = {"uuid": profile_path.stem, "alias": None, "bio": None}

    for i, line in enumerate(lines):
        if line.strip() == "## Display Preferences":
            profile["alias"] = _extract_alias_from_lines(lines, i)
        elif line.strip() == "## Bio":
            profile["bio"] = _extract_bio_from_lines(lines, i)

    return profile


def load_comments_for_post(post_id: str, store: RankingStore) -> str | None:
    """Load existing comments for a post.

    Args:
        post_id: Post ID
        store: Ranking store

    Returns:
        Formatted comment summary or None

    """
    comparisons = store.get_comments_for_post(post_id)
    # Check if empty (comparisons is an Ibis table, can't use "if not")
    if comparisons is None or int(comparisons.count().execute()) == 0:
        return None
    comment_list = []
    for comp in comparisons[-5:]:
        comp["comparison_id"]
        timestamp = comp["timestamp"]
        profile_id = comp["profile_id"]
        if comp["post_a"] == post_id:
            comment = comp["comment_a"]
            stars = comp["stars_a"]
        else:
            comment = comp["comment_b"]
            stars = comp["stars_b"]
        stars_str = "⭐" * stars
        comment_list.append(f"**{profile_id}** ({timestamp}): {stars_str}\n> {comment}")
    return "\n\n".join(comment_list)


def _find_post_path(posts_dir: Path, post_id: str) -> Path:
    """Find full path to post file given its ID (stem).

    Args:
        posts_dir: Directory containing posts
        post_id: Post ID (filename without extension)

    Returns:
        Full path to post file

    Raises:
        ValueError: If post not found or ambiguous

    """
    candidates = list(posts_dir.rglob("*.md"))
    matches = [candidate for candidate in candidates if candidate.stem == post_id]
    if matches:
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            matches_str = ", ".join(str(match) for match in matches)
            msg = f"Multiple posts found for {post_id}: {matches_str}"
            raise ValueError(msg)
        return matches[0]
    searched = ", ".join(str(candidate.parent) for candidate in candidates if candidate.parent)
    msg = f"Post not found for id '{post_id}'. Looked in: {searched}"
    raise ValueError(msg)


def save_comparison(store: RankingStore, comparison: ComparisonData) -> None:
    """Save comparison results to store."""
    comparison_data = {
        "comparison_id": str(uuid.uuid4()),
        "timestamp": datetime.now(UTC),
        "profile_id": comparison.profile_id,
        "post_a": comparison.post_a,
        "post_b": comparison.post_b,
        "winner": comparison.winner,
        "comment_a": comparison.comment_a,
        "stars_a": comparison.stars_a,
        "comment_b": comparison.comment_b,
        "stars_b": comparison.stars_b,
    }
    store.save_comparison(comparison_data)


def _truncate_comment(comment: str) -> str:
    """Truncate comment to max length."""
    if len(comment) > MAX_COMMENT_LENGTH:
        truncate_at = MAX_COMMENT_LENGTH - len(COMMENT_TRUNCATE_SUFFIX)
        return comment[:truncate_at] + COMMENT_TRUNCATE_SUFFIX
    return comment


def _validate_ratings_exist(rating_a: dict[str, Any] | None, rating_b: dict[str, Any] | None) -> None:
    """Validate that ratings exist for both posts.

    Args:
        rating_a: Rating for post A
        rating_b: Rating for post B

    Raises:
        ValueError: If either rating is missing

    """
    if rating_a is None or rating_b is None:
        msg = "Missing ratings for posts despite initialization"
        raise ValueError(msg)


def _register_ranking_tools(agent: Agent) -> None:
    """Register all ranking tools on the agent."""

    @agent.tool
    def choose_winner_tool(ctx: RunContext[RankingAgentState], winner: str) -> WinnerChoice:
        """Declare which post is better overall.

        Args:
            winner: Which post is better - must be either "A" or "B"

        """
        if winner not in ("A", "B"):
            msg = f"Winner must be 'A' or 'B', got: {winner}"
            raise ValueError(msg)
        console.print(f"[green]Winner: Post {winner}[/green]")
        return WinnerChoice(winner=winner)

    @agent.tool
    def comment_post_a_tool(ctx: RunContext[RankingAgentState], comment: str, stars: int) -> PostComment:
        """Provide detailed feedback on Post A.

        Args:
            comment: Markdown comment, max 250 chars. Reference existing comments if relevant
            stars: Star rating 1-5

        """
        if not MIN_STARS <= stars <= MAX_STARS:
            msg = f"Stars must be {MIN_STARS}-{MAX_STARS}, got: {stars}"
            raise ValueError(msg)
        comment = _truncate_comment(comment)
        console.print(f"[yellow]Comment A: {comment}[/yellow]")
        console.print(f"[yellow]Stars A: {'⭐' * stars}[/yellow]")
        return PostComment(comment=comment, stars=stars)

    @agent.tool
    def comment_post_b_tool(ctx: RunContext[RankingAgentState], comment: str, stars: int) -> PostComment:
        """Provide detailed feedback on Post B.

        Args:
            comment: Markdown comment, max 250 chars. Reference existing comments if relevant
            stars: Star rating 1-5

        """
        if not MIN_STARS <= stars <= MAX_STARS:
            msg = f"Stars must be {MIN_STARS}-{MAX_STARS}, got: {stars}"
            raise ValueError(msg)
        comment = _truncate_comment(comment)
        console.print(f"[yellow]Comment B: {comment}[/yellow]")
        console.print(f"[yellow]Stars B: {'⭐' * stars}[/yellow]")
        return PostComment(comment=comment, stars=stars)


async def run_comparison_with_pydantic_agent(config: ComparisonConfig) -> dict[str, Any]:
    """Run a three-turn comparison between two posts using Pydantic AI agent.

    Args:
        config: Configuration for running the comparison

    Returns:
        dict with comparison results (winner, comments, stars, ratings)

    """
    rankings_dir = config.site_dir / "rankings"
    store = RankingStore(rankings_dir)
    site_paths = resolve_site_paths(config.site_dir)
    posts_dir = site_paths.posts_dir
    post_a_path = _find_post_path(posts_dir, config.post_a_id)
    post_b_path = _find_post_path(posts_dir, config.post_b_id)
    content_a = load_post_content(post_a_path)
    content_b = load_post_content(post_b_path)
    profile = load_profile(config.profile_path)
    existing_comments_a = load_comments_for_post(config.post_a_id, store)
    existing_comments_b = load_comments_for_post(config.post_b_id, store)
    state = RankingAgentState(
        post_a_id=config.post_a_id,
        post_b_id=config.post_b_id,
        content_a=content_a,
        content_b=content_b,
        profile=profile,
        existing_comments_a=existing_comments_a,
        existing_comments_b=existing_comments_b,
        store=store,
        site_dir=config.site_dir,
    )
    comments_a_display = existing_comments_a or "No comments yet. Be the first!"
    comments_b_display = existing_comments_b or "No comments yet. Be the first!"
    alias_or_uuid = profile.get("alias") or profile["uuid"]

    # Generate prompt from Jinja template
    prompt_template = RankingComparisonPromptTemplate(
        alias_or_uuid=alias_or_uuid,
        bio=profile.get("bio"),
        post_a_id=config.post_a_id,
        content_a=content_a,
        post_b_id=config.post_b_id,
        content_b=content_b,
        comments_a_display=comments_a_display,
        comments_b_display=comments_b_display,
        prompts_dir=config.prompts_dir,
    )
    prompt = prompt_template.render()
    with logfire_span("ranking_agent", post_a=config.post_a_id, post_b=config.post_b_id, model=config.model):
        if config.agent_model is None:
            if config.api_key:
                os.environ["GOOGLE_API_KEY"] = config.api_key
            model_instance = config.model
        else:
            model_instance = config.agent_model
        # Generate system prompt from Jinja template
        system_prompt_template = RankingSystemPromptTemplate(prompts_dir=config.prompts_dir)
        system_prompt = system_prompt_template.render()

        agent = Agent[RankingAgentState, str](
            model=model_instance,
            deps_type=RankingAgentState,
            system_prompt=system_prompt,
        )
        _register_ranking_tools(agent)
        try:
            result = await agent.run(prompt, deps=state)

            # Extract results from message history
            ranking_result = _extract_ranking_results(result.all_messages())

            comparison = ComparisonData(
                profile_id=profile["uuid"],
                post_a=config.post_a_id,
                post_b=config.post_b_id,
                winner=ranking_result.winner,
                comment_a=ranking_result.comment_a,
                stars_a=ranking_result.stars_a,
                comment_b=ranking_result.comment_b,
                stars_b=ranking_result.stars_b,
            )
            save_comparison(store=store, comparison=comparison)
            rating_a = store.get_rating(config.post_a_id)
            rating_b = store.get_rating(config.post_b_id)
            _validate_ratings_exist(rating_a, rating_b)
            new_elo_a, new_elo_b = calculate_elo_update(
                rating_a["elo_global"], rating_b["elo_global"], ranking_result.winner
            )
            store.update_ratings(config.post_a_id, config.post_b_id, new_elo_a, new_elo_b)
        except Exception as e:
            console.print(f"[red]Ranking agent failed: {e}[/red]")
            msg = "Ranking agent execution failed"
            raise RuntimeError(msg) from e
        else:
            return {
                "winner": ranking_result.winner,
                "comment_a": ranking_result.comment_a,
                "stars_a": ranking_result.stars_a,
                "comment_b": ranking_result.comment_b,
                "stars_b": ranking_result.stars_b,
            }
