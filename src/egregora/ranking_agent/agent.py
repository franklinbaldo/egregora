"""LLM agent for rating and comparing blog posts."""

from pydantic import BaseModel, Field
from typing import List
from pathlib import Path
import random
from datetime import datetime

import polars as pl
from google import genai

from .elo import init_ratings, select_posts_to_rate, update_ratings


class RatePost(BaseModel):
    """Rates a blog post on a scale of 1 to 5."""
    post_filename: str = Field(..., description="The filename of the post being rated.")
    rating: int = Field(..., ge=1, le=5, description="The rating from 1 to 5.")

class ChooseWinner(BaseModel):
    """Chooses the winning post from a pair."""
    winning_post_filename: str = Field(..., description="The filename of the winning post.")

class AddComment(BaseModel):
    """Adds a comment to a blog post."""
    post_filename: str = Field(..., description="The filename of the post being commented on.")
    comment: str = Field(..., max_length=250, description="The comment, limited to 250 characters.")

async def get_ratings_from_llm(
    profile: str,
    post1_content: str,
    post2_content: str,
    post1_filename: str,
    post2_filename: str,
    client: genai.Client,
) -> List[BaseModel]:
    """Gets ratings and comments from the LLM."""

    prompt = f"""
You are an expert blog reader. Your personality is:
---
{profile}
---

You are tasked with comparing two blog posts and providing your feedback.
The two posts are:

**Post 1: {post1_filename}**
---
{post1_content}
---

**Post 2: {post2_filename}**
---
{post2_content}
---

Based on your personality, please perform the following actions:
1. Rate each post on a scale of 1 to 5 stars.
2. Choose which of the two posts you prefer.
3. Write a brief comment (under 250 characters) for each post.
"""

    model = client.get_model("models/gemini-1.5-flash")

    response = await model.generate_content_async(
        prompt,
        tools=[RatePost, ChooseWinner, AddComment],
    )

    tools = []
    for part in response.parts:
        if part.function_call:
            tool_name = part.function_call.name
            tool_args = part.function_call.args

            if tool_name == "RatePost":
                tools.append(RatePost(**tool_args))
            elif tool_name == "ChooseWinner":
                tools.append(ChooseWinner(**tool_args))
            elif tool_name == "AddComment":
                tools.append(AddComment(**tool_args))

    return tools

async def run_ranking(
    posts_dir: Path,
    profiles_dir: Path,
    output_dir: Path,
    gemini_api_key: str,
):
    """Main runner for the ranking process."""
    client = genai.Client(api_key=gemini_api_key)

    # Initialize ratings
    ratings_path = output_dir / "elo_ratings.parquet"
    ratings_df = init_ratings(posts_dir, ratings_path)

    # Select posts
    post1_filename, post2_filename = select_posts_to_rate(ratings_df)
    post1_path = posts_dir / post1_filename
    post2_path = posts_dir / post2_filename

    # Load profile
    profiles = list(profiles_dir.glob("*.md"))
    profile_path = random.choice(profiles)

    # Get ratings
    results = await get_ratings_from_llm(
        profile=profile_path.read_text(),
        post1_content=post1_path.read_text(),
        post2_content=post2_path.read_text(),
        post1_filename=post1_filename,
        post2_filename=post2_filename,
        client=client,
    )

    # Process results
    winner = None
    loser = None

    for result in results:
        if isinstance(result, ChooseWinner):
            winner = result.winning_post_filename
            loser = post2_filename if winner == post1_filename else post1_filename

    # Update and save ratings
    ratings_df = update_ratings(ratings_df, winner, loser)
    ratings_df.write_parquet(ratings_path)

    # Save history
    history_path = output_dir / "elo_history.parquet"
    history_df = pl.DataFrame({
        "timestamp": [datetime.now()],
        "profile": [profile_path.name],
        "post1": [post1_filename],
        "post2": [post2_filename],
        "winner": [winner],
        "tools_output": [str(results)],
    })

    if history_path.exists():
        existing_history = pl.read_parquet(history_path)
        history_df = existing_history.vstack(history_df)

    history_df.write_parquet(history_path)
