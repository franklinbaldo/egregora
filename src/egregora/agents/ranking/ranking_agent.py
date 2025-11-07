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
    comment_a: str | None = None
    stars_a: int | None = None
    comment_b: str | None = None
    stars_b: int | None = None

    # Try to iterate through messages
    try:
        for message in messages:
            # Check if this is a tool return message
            if hasattr(message, "kind") and message.kind == "tool-return":
                # Parse the content - it might be JSON or a Pydantic model
                content = message.content
                if isinstance(content, str):
                    try:
                        data = json.loads(content)
                    except (json.JSONDecodeError, ValueError):
                        continue
                elif hasattr(content, "model_dump"):
                    data = content.model_dump()
                elif hasattr(content, "__dict__"):
                    data = vars(content)
                else:
                    data = content

                # Extract results based on tool name
                if isinstance(data, dict):
                    # WinnerChoice has just 'winner' field
                    if "winner" in data and "comment" not in data and "stars" not in data:
                        winner = data["winner"]
                    # PostComment has 'comment' and 'stars' fields
                    elif "comment" in data and "stars" in data:
                        # Need to determine if this is comment_a or comment_b
                        # Look at tool name in message
                        tool_name = getattr(message, "tool_name", None) or ""
                        if "post_a" in tool_name.lower() and comment_a is None:
                            comment_a = data["comment"]
                            stars_a = data["stars"]
                        elif "post_b" in tool_name.lower() and comment_b is None:
                            comment_b = data["comment"]
                            stars_b = data["stars"]
                        elif comment_a is None:
                            # First comment seen, assume it's A
                            comment_a = data["comment"]
                            stars_a = data["stars"]
                        elif comment_b is None:
                            # Second comment seen, assume it's B
                            comment_b = data["comment"]
                            stars_b = data["stars"]
    except (AttributeError, TypeError) as e:
        logger.debug("Could not parse tool results: %s", e)

    # Validate all results were found
    if winner is None:
        msg = "Agent did not choose a winner"
        raise ValueError(msg)
    if comment_a is None or stars_a is None:
        msg = "Agent did not comment on Post A"
        raise ValueError(msg)
    if comment_b is None or stars_b is None:
        msg = "Agent did not comment on Post B"
        raise ValueError(msg)

    return RankingResult(
        winner=winner, comment_a=comment_a, stars_a=stars_a, comment_b=comment_b, stars_b=stars_b
    )


def load_post_content(post_path: Path) -> str:
    """Load markdown content from a blog post, excluding front matter."""
    content = post_path.read_text()
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= FRONTMATTER_PARTS:
            return parts[2].strip()
    return content.strip()


def load_profile(profile_path: Path) -> dict[str, Any]:
    """Load author profile metadata."""
    content = profile_path.read_text()
    profile = {"uuid": profile_path.stem, "alias": None, "bio": None}
    if "## Display Preferences" in content:
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip() == "## Display Preferences":
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].strip().startswith("- Alias:"):
                        alias = lines[j].split("- Alias:", 1)[1].strip()
                        profile["alias"] = alias
                        break
                break
    if "## Bio" in content:
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip() == "## Bio":
                bio_lines = []
                for j in range(i + 2, len(lines)):
                    if lines[j].strip().startswith("##"):
                        break
                    bio_lines.append(lines[j])
                profile["bio"] = "\n".join(bio_lines).strip()
                break
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


def save_comparison(
    store: RankingStore,
    profile_id: str,
    post_a: str,
    post_b: str,
    winner: str,
    comment_a: str,
    stars_a: int,
    comment_b: str,
    stars_b: int,
) -> None:
    """Save comparison results to store."""
    comparison_data = {
        "comparison_id": str(uuid.uuid4()),
        "timestamp": datetime.now(UTC),
        "profile_id": profile_id,
        "post_a": post_a,
        "post_b": post_b,
        "winner": winner,
        "comment_a": comment_a,
        "stars_a": stars_a,
        "comment_b": comment_b,
        "stars_b": stars_b,
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


async def run_comparison_with_pydantic_agent(
    site_dir: Path,
    post_a_id: str,
    post_b_id: str,
    profile_path: Path,
    api_key: str,
    model: str = "models/gemini-flash-latest",
    agent_model: object | None = None,  # Test model injection - accepts any Pydantic AI compatible model
) -> dict[str, Any]:
    """Run a three-turn comparison between two posts using Pydantic AI agent.

    Args:
        site_dir: Root directory of MkDocs site
        post_a_id: Post ID (filename stem) for post A
        post_b_id: Post ID (filename stem) for post B
        profile_path: Path to profile to impersonate
        api_key: Gemini API key
        model: Model name to use (default: models/gemini-flash-latest)
        agent_model: Optional test model for deterministic tests

    Returns:
        dict with comparison results (winner, comments, stars, ratings)

    """
    rankings_dir = site_dir / "rankings"
    store = RankingStore(rankings_dir)
    site_paths = resolve_site_paths(site_dir)
    posts_dir = site_paths.posts_dir
    post_a_path = _find_post_path(posts_dir, post_a_id)
    post_b_path = _find_post_path(posts_dir, post_b_id)
    content_a = load_post_content(post_a_path)
    content_b = load_post_content(post_b_path)
    profile = load_profile(profile_path)
    existing_comments_a = load_comments_for_post(post_a_id, store)
    existing_comments_b = load_comments_for_post(post_b_id, store)
    state = RankingAgentState(
        post_a_id=post_a_id,
        post_b_id=post_b_id,
        content_a=content_a,
        content_b=content_b,
        profile=profile,
        existing_comments_a=existing_comments_a,
        existing_comments_b=existing_comments_b,
        store=store,
        site_dir=site_dir,
    )
    comments_a_display = existing_comments_a or "No comments yet. Be the first!"
    comments_b_display = existing_comments_b or "No comments yet. Be the first!"
    alias_or_uuid = profile.get("alias") or profile["uuid"]
    prompt = f"You are {alias_or_uuid}, impersonating their reading style and preferences.\n\nProfile bio: {profile.get('bio') or 'No bio available'}\n\nYou will complete a three-turn comparison:\n\n# Turn 1: Choose Winner\nRead these two blog posts and decide which one is better overall.\n\n## Post A: {post_a_id}\n{content_a}\n\n## Post B: {post_b_id}\n{content_b}\n\nUse the choose_winner tool to declare the winner.\n\n# Turn 2: Comment on Post A\nProvide detailed feedback on Post A.\n\n## What others have said about Post A:\n{comments_a_display}\n\nUse the comment_post_a tool to:\n- Rate it (1-5 stars)\n- Write a comment (max 250 chars, markdown supported)\n- Reference existing comments if relevant\n\n# Turn 3: Comment on Post B\nProvide detailed feedback on Post B.\n\n## What others have said about Post B:\n{comments_b_display}\n\nUse the comment_post_b tool to:\n- Rate it (1-5 stars)\n- Write a comment (max 250 chars, markdown supported)\n- Reference existing comments if relevant\n\nComplete all three turns: choose_winner, comment_post_a, comment_post_b."
    with logfire_span("ranking_agent", post_a=post_a_id, post_b=post_b_id, model=model):
        if agent_model is None:
            if api_key:
                os.environ["GOOGLE_API_KEY"] = api_key
            model_instance = model
        else:
            model_instance = agent_model
        agent = Agent[RankingAgentState, str](
            model=model_instance,
            deps_type=RankingAgentState,
            system_prompt="You are a blog post critic providing detailed comparisons.",
        )
        _register_ranking_tools(agent)
        try:
            result = await agent.run(prompt, deps=state)

            # Extract results from message history
            ranking_result = _extract_ranking_results(result.all_messages())

            save_comparison(
                store=store,
                profile_id=profile["uuid"],
                post_a=post_a_id,
                post_b=post_b_id,
                winner=ranking_result.winner,
                comment_a=ranking_result.comment_a,
                stars_a=ranking_result.stars_a,
                comment_b=ranking_result.comment_b,
                stars_b=ranking_result.stars_b,
            )
            rating_a = store.get_rating(post_a_id)
            rating_b = store.get_rating(post_b_id)
            _validate_ratings_exist(rating_a, rating_b)
            new_elo_a, new_elo_b = calculate_elo_update(
                rating_a["elo_global"], rating_b["elo_global"], ranking_result.winner
            )
            store.update_ratings(post_a_id, post_b_id, new_elo_a, new_elo_b)
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
