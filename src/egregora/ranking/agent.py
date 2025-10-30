"""LLM-based ranking agent using three-turn conversation protocol."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from google import genai
from google.genai import types as genai_types
from rich.console import Console
from typing import Any

from .elo import calculate_elo_update
from ..utils import call_with_retries_sync
from .store import RankingStore

console = Console()

# Constants
FRONTMATTER_PARTS = 3
MAX_COMMENT_LENGTH = 250
COMMENT_TRUNCATE_SUFFIX = "..."


# Tool definitions for Gemini function calling (new SDK format)
CHOOSE_WINNER_TOOL = genai_types.Tool(
    function_declarations=[
        genai_types.FunctionDeclaration(
            name="choose_winner",
            description="Declare which post is better overall",
            parameters=genai_types.Schema(
                type=genai_types.Type.OBJECT,
                properties={
                    "winner": genai_types.Schema(
                        type=genai_types.Type.STRING,
                        enum=["A", "B"],
                        description="Which post is better: A or B",
                    )
                },
                required=["winner"],
            ),
        )
    ]
)

COMMENT_POST_A_TOOL = genai_types.Tool(
    function_declarations=[
        genai_types.FunctionDeclaration(
            name="comment_post_A",
            description="Provide detailed feedback on Post A",
            parameters=genai_types.Schema(
                type=genai_types.Type.OBJECT,
                properties={
                    "comment": genai_types.Schema(
                        type=genai_types.Type.STRING,
                        description="Markdown comment, max 250 chars. Reference existing comments if relevant.",
                    ),
                    "stars": genai_types.Schema(
                        type=genai_types.Type.INTEGER,
                        description="Star rating 1-5",
                        minimum=1,
                        maximum=5,
                    ),
                },
                required=["comment", "stars"],
            ),
        )
    ],
)

COMMENT_POST_B_TOOL = genai_types.Tool(
    function_declarations=[
        genai_types.FunctionDeclaration(
            name="comment_post_B",
            description="Provide detailed feedback on Post B",
            parameters=genai_types.Schema(
                type=genai_types.Type.OBJECT,
                properties={
                    "comment": genai_types.Schema(
                        type=genai_types.Type.STRING,
                        description="Markdown comment, max 250 chars. Reference existing comments if relevant.",
                    ),
                    "stars": genai_types.Schema(
                        type=genai_types.Type.INTEGER,
                        description="Star rating 1-5",
                        minimum=1,
                        maximum=5,
                    ),
                },
                required=["comment", "stars"],
            ),
        )
    ],
)
    
    
    


def load_post_content(post_path: Path) -> str:
    """Load markdown content from a blog post, excluding front matter."""
    content = post_path.read_text()

    # Skip front matter if present
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= FRONTMATTER_PARTS:
            return parts[2].strip()

    return content.strip()


def load_profile(profile_path: Path) -> dict[str, Any]:
    """Load author profile metadata."""
    content = profile_path.read_text()

    profile = {
        "uuid": profile_path.stem,
        "alias": None,
        "bio": None,
    }

    # Extract alias
    if "## Display Preferences" in content:
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip() == "## Display Preferences":
                # Look for alias in next few lines
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].strip().startswith("- Alias:"):
                        alias = lines[j].split("- Alias:", 1)[1].strip()
                        profile["alias"] = alias
                        break

    # Extract bio
    if "## Bio" in content:
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip() == "## Bio":
                # Look for bio in next few lines
                for j in range(i + 1, min(i + 10, len(lines))):
                    if lines[j].strip() and not lines[j].startswith("#"):
                        profile["bio"] = lines[j].strip()
                        break

    return profile


def load_comments_for_post(post_id: str, store: RankingStore) -> str | None:
    """
    Load all existing comments for a post from DuckDB.
    Format as markdown for agent context.
    """
    comments_df = store.get_comments_for_post(post_id)

    if len(comments_df) == 0:
        return None

    # Format as markdown
    lines = []
    for row in comments_df.iter_rows(named=True):
        # Get profile alias (use short UUID for now)
        profile_name = row["profile_id"][:8]
        stars = "⭐" * row["stars"]
        timestamp = row["timestamp"].strftime("%Y-%m-%d")

        lines.append(f"**@{profile_name}** {stars} ({timestamp})")
        lines.append(f"> {row['comment']}")
        lines.append("")

    return "\n".join(lines)


def save_comparison(  # noqa: PLR0913
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


def _load_comparison_posts(site_dir: Path, post_a_id: str, post_b_id: str) -> tuple[str, str]:
    """Load content for both posts."""
    posts_dir = site_dir / "posts"

    post_a_path = posts_dir / f"{post_a_id}.md"
    post_b_path = posts_dir / f"{post_b_id}.md"

    if not post_a_path.exists():
        raise ValueError(f"Post not found: {post_a_path}")
    if not post_b_path.exists():
        raise ValueError(f"Post not found: {post_b_path}")

    content_a = load_post_content(post_a_path)
    content_b = load_post_content(post_b_path)

    return content_a, content_b


def _extract_tool_call_result(response: genai_types.GenerateContentResponse, tool_name: str, arg_names: list[str]) -> dict[str, Any] | None:
    """Extract tool call arguments from LLM response."""
    if not response.candidates:
        return None
    if not response.candidates[0].content:
        return None
    if not response.candidates[0].content.parts:
        return None

    for part in response.candidates[0].content.parts:
        if hasattr(part, "function_call") and part.function_call and part.function_call.args and part.function_call.name == tool_name:
            return {arg: part.function_call.args[arg] for arg in arg_names}

    return None


def _run_turn1_choose_winner(  # noqa: PLR0913 # type: ignore[no-untyped-def]
    client: genai.Client,
    model: str,
    profile: dict[str, Any],
    post_a_id: str,
    post_b_id: str,
    content_a: str,
    content_b: str,
) -> str:
    """Run turn 1: Choose winner."""
    console.print("\n[bold cyan]Turn 1: Choosing winner...[/bold cyan]")

    turn1_prompt = f"""You are {profile.get("alias") or profile["uuid"]}, impersonating their reading style and preferences.

Profile bio: {profile.get("bio") or "No bio available"}

Read these two blog posts and decide which one is better overall.

# Post A: {post_a_id}
{content_a}

# Post B: {post_b_id}
{content_b}

Use the choose_winner tool to declare the winner."""

    turn1_response = call_with_retries_sync(
        client.models.generate_content,
        model=model,
        contents=[genai_types.Content(role="user", parts=[genai_types.Part(text=turn1_prompt)])],
        config=genai_types.GenerateContentConfig(tools=[CHOOSE_WINNER_TOOL]),
    )

    result = _extract_tool_call_result(turn1_response, "choose_winner", ["winner"])
    if not result:
        raise ValueError("Agent did not call choose_winner tool")

    winner = result["winner"]
    console.print(f"[green]Winner: Post {winner}[/green]")
    return winner


def _run_turn2_comment_post_a(  # noqa: PLR0913
    client: genai.Client,
    model: str,
    winner: str,
    post_a_id: str,
    content_a: str,
    existing_comments_a: str | None,
) -> tuple[str, int]:
    """Run turn 2: Comment on Post A."""
    console.print("\n[bold cyan]Turn 2: Commenting on Post A...[/bold cyan]")

    comments_display = existing_comments_a or "No comments yet. Be the first!"

    turn2_prompt = f"""You chose Post {winner} as the winner.

Now provide detailed feedback on Post A.

# Post A: {post_a_id}
{content_a}

# What others have said about Post A:
{comments_display}

Use the comment_post_A tool to:
- Rate it (1-5 stars)
- Write a comment (max 250 chars, markdown supported)
- Reference existing comments if relevant"""

    turn2_response = call_with_retries_sync(
        client.models.generate_content,
        model=model,
        contents=[genai_types.Content(role="user", parts=[genai_types.Part(text=turn2_prompt)])],
        config=genai_types.GenerateContentConfig(tools=[COMMENT_POST_A_TOOL]),
    )

    result = _extract_tool_call_result(turn2_response, "comment_post_A", ["comment", "stars"])
    if not result:
        raise ValueError("Agent did not call comment_post_A tool")

    comment_a = result["comment"]
    stars_a = int(result["stars"])

    # Truncate comment
    if len(comment_a) > MAX_COMMENT_LENGTH:
        truncate_at = MAX_COMMENT_LENGTH - len(COMMENT_TRUNCATE_SUFFIX)
        comment_a = comment_a[:truncate_at] + COMMENT_TRUNCATE_SUFFIX

    console.print(f"[yellow]Comment A: {comment_a}[/yellow]")
    console.print(f"[yellow]Stars A: {'⭐' * stars_a}[/yellow]")

    return comment_a, stars_a


def _run_turn3_comment_post_b(  # noqa: PLR0913
    client: genai.Client,
    model: str,
    winner: str,
    post_b_id: str,
    content_b: str,
    existing_comments_b: str | None,
) -> tuple[str, int]:
    """Run turn 3: Comment on Post B."""
    console.print("\n[bold cyan]Turn 3: Commenting on Post B...[/bold cyan]")

    comments_display = existing_comments_b or "No comments yet. Be the first!"

    turn3_prompt = f"""You chose Post {winner} as the winner.

Now provide detailed feedback on Post B.

# Post B: {post_b_id}
{content_b}

# What others have said about Post B:
{comments_display}

Use the comment_post_B tool to:
- Rate it (1-5 stars)
- Write a comment (max 250 chars, markdown supported)
- Reference existing comments if relevant"""

    turn3_response = call_with_retries_sync(
        client.models.generate_content,
        model=model,
        contents=[genai_types.Content(role="user", parts=[genai_types.Part(text=turn3_prompt)])],
        config=genai_types.GenerateContentConfig(tools=[COMMENT_POST_B_TOOL]),
    )

    result = _extract_tool_call_result(turn3_response, "comment_post_B", ["comment", "stars"])
    if not result:
        raise ValueError("Agent did not call comment_post_B tool")

    comment_b = result["comment"]
    stars_b = int(result["stars"])

    # Truncate comment
    if len(comment_b) > MAX_COMMENT_LENGTH:
        truncate_at = MAX_COMMENT_LENGTH - len(COMMENT_TRUNCATE_SUFFIX)
        comment_b = comment_b[:truncate_at] + COMMENT_TRUNCATE_SUFFIX

    console.print(f"[yellow]Comment B: {comment_b}[/yellow]")
    console.print(f"[yellow]Stars B: {'⭐' * stars_b}[/yellow]")

    return comment_b, stars_b


def run_comparison(  # noqa: PLR0913
    site_dir: Path,
    post_a_id: str,
    post_b_id: str,
    profile_path: Path,
    api_key: str,
    model: str = "models/gemini-flash-latest",
) -> dict[str, Any]:
    """
    Run a three-turn comparison between two posts.

    Args:
        site_dir: Root directory of MkDocs site
        post_a_id: Post ID (filename stem) for post A
        post_b_id: Post ID (filename stem) for post B
        profile_path: Path to profile to impersonate
        api_key: Gemini API key
        model: Model name to use (default: models/gemini-flash-latest)

    Returns:
        dict with comparison results
    """
    # Setup
    rankings_dir = site_dir / "rankings"
    store = RankingStore(rankings_dir)
    client = genai.Client(api_key=api_key)

    # Load data
    content_a, content_b = _load_comparison_posts(site_dir, post_a_id, post_b_id)

    profile = load_profile(profile_path)
    existing_comments_a = load_comments_for_post(post_a_id, store)
    existing_comments_b = load_comments_for_post(post_b_id, store)

    # Run three-turn comparison
    winner = _run_turn1_choose_winner(
        client, model, profile, post_a_id, post_b_id, content_a, content_b
    )

    comment_a, stars_a = _run_turn2_comment_post_a(
        client, model, winner, post_a_id, content_a, existing_comments_a
    )

    comment_b, stars_b = _run_turn3_comment_post_b(
        client, model, winner, post_b_id, content_b, existing_comments_b
    )

    # Save results
    save_comparison(
        store=store,
        profile_id=profile["uuid"],
        post_a=post_a_id,
        post_b=post_b_id,
        winner=winner,
        comment_a=comment_a,
        stars_a=stars_a,
        comment_b=comment_b,
        stars_b=stars_b,
    )

    # Update ELO ratings
    rating_a = store.get_rating(post_a_id)
    rating_b = store.get_rating(post_b_id)

    if rating_a is None or rating_b is None:
        msg = "Missing ratings for posts despite initialization"
        raise ValueError(msg)

    new_elo_a, new_elo_b = calculate_elo_update(
        rating_a["elo_global"], rating_b["elo_global"], winner
    )
    store.update_ratings(post_a_id, post_b_id, new_elo_a, new_elo_b)

    return {
        "winner": winner,
        "comment_a": comment_a,
        "stars_a": stars_a,
        "comment_b": comment_b,
        "stars_b": stars_b,
    }
