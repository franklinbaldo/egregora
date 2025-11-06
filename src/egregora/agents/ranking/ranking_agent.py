"""Pydantic AI-powered ranking agent using three-turn conversation protocol.

This module migrates the ranking agent from google.genai to Pydantic AI,
maintaining the same three-turn protocol:
1. Choose winner (A or B)
2. Comment on Post A (stars + comment)
3. Comment on Post B (stars + comment)
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent, RunContext
from rich.console import Console

from egregora.agents.ranking.elo import calculate_elo_update
from egregora.agents.ranking.store import RankingStore
from egregora.config import resolve_site_paths
from egregora.utils.logfire_config import logfire_span

if TYPE_CHECKING:
    from pathlib import Path
console = Console()
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
    """State passed to ranking agent tools."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    post_a_id: str
    post_b_id: str
    content_a: str
    content_b: str
    profile: dict[str, Any]
    existing_comments_a: str | None
    existing_comments_b: str | None
    store: RankingStore
    site_dir: Path
    winner: str | None = None
    comment_a: str | None = None
    stars_a: int | None = None
    comment_b: str | None = None
    stars_b: int | None = None


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
    if "## Bio" in content:
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip() == "## Bio":
                for j in range(i + 1, min(i + 10, len(lines))):
                    if lines[j].strip() and (not lines[j].startswith("#")):
                        profile["bio"] = lines[j].strip()
                        break
    return profile


def load_comments_for_post(post_id: str, store: RankingStore) -> str | None:
    """Load all existing comments for a post from DuckDB.

    Format as markdown for agent context.
    """
    comments_table = store.get_comments_for_post(post_id)
    if comments_table.count().execute() == 0:
        return None
    lines = []
    for row in comments_table.iter_rows(named=True):
        profile_name = row["profile_id"][:8]
        stars = "⭐" * row["stars"]
        timestamp = row["timestamp"].strftime("%Y-%m-%d")
        lines.append(f"**@{profile_name}** {stars} ({timestamp})")
        lines.append(f"> {row['comment']}")
        lines.append("")
    return "\n".join(lines)


def _find_post_path(posts_dir: Path, post_id: str) -> Path:
    """Locate a post file within the MkDocs posts directory."""
    candidates: list[Path] = []
    search_dirs: list[Path] = []
    if posts_dir.name == ".posts":
        search_dirs.append(posts_dir)
        search_dirs.append(posts_dir.parent)
    else:
        search_dirs.append(posts_dir / ".posts")
        search_dirs.append(posts_dir)
    for directory in search_dirs:
        if not directory.exists():
            continue
        direct_candidate = directory / f"{post_id}.md"
        candidates.append(direct_candidate)
        if direct_candidate.exists():
            return direct_candidate
        matches = list(directory.rglob(f"{post_id}.md"))
        candidates.extend(matches)
        if matches:
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
    """Save comparison result to DuckDB."""
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
        ctx.deps.winner = winner
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
        ctx.deps.comment_a = comment
        ctx.deps.stars_a = stars
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
        ctx.deps.comment_b = comment
        ctx.deps.stars_b = stars
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
    agent_model: Any | None = None,
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
            await agent.run(prompt, deps=state)
            if state.winner is None:
                msg = "Agent did not choose a winner"
                raise ValueError(msg)
            if state.comment_a is None or state.stars_a is None:
                msg = "Agent did not comment on Post A"
                raise ValueError(msg)
            if state.comment_b is None or state.stars_b is None:
                msg = "Agent did not comment on Post B"
                raise ValueError(msg)
            save_comparison(
                store=store,
                profile_id=profile["uuid"],
                post_a=post_a_id,
                post_b=post_b_id,
                winner=state.winner,
                comment_a=state.comment_a,
                stars_a=state.stars_a,
                comment_b=state.comment_b,
                stars_b=state.stars_b,
            )
            rating_a = store.get_rating(post_a_id)
            rating_b = store.get_rating(post_b_id)
            if rating_a is None or rating_b is None:
                msg = "Missing ratings for posts despite initialization"
                raise ValueError(msg)
            new_elo_a, new_elo_b = calculate_elo_update(
                rating_a["elo_global"], rating_b["elo_global"], state.winner
            )
            store.update_ratings(post_a_id, post_b_id, new_elo_a, new_elo_b)
        except Exception as e:
            console.print(f"[red]Ranking agent failed: {e}[/red]")
            msg = "Ranking agent execution failed"
            raise RuntimeError(msg) from e
        else:
            return {
                "winner": state.winner,
                "comment_a": state.comment_a,
                "stars_a": state.stars_a,
                "comment_b": state.comment_b,
                "stars_b": state.stars_b,
            }
