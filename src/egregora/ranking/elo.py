"""ELO rating system for blog post quality ranking."""

from pathlib import Path
from datetime import datetime, timezone
import polars as pl


DEFAULT_ELO = 1500
K_FACTOR = 32


def calculate_expected_score(rating_a: float, rating_b: float) -> tuple[float, float]:
    """
    Calculate expected scores for two players.

    Returns:
        (expected_a, expected_b): Expected scores (0-1) for each player
    """
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    return expected_a, expected_b


def calculate_elo_update(
    rating_a: float,
    rating_b: float,
    winner: str,
    k_factor: int = K_FACTOR
) -> tuple[float, float]:
    """
    Calculate new ELO ratings after a comparison.

    Args:
        rating_a: Current ELO rating for post A
        rating_b: Current ELO rating for post B
        winner: "A" or "B" (which post won)
        k_factor: K-factor for ELO calculation (default 32)

    Returns:
        (new_rating_a, new_rating_b): Updated ELO ratings
    """
    expected_a, expected_b = calculate_expected_score(rating_a, rating_b)

    # Actual scores (1 for winner, 0 for loser)
    actual_a = 1.0 if winner == "A" else 0.0
    actual_b = 1.0 if winner == "B" else 0.0

    # Update ratings
    new_rating_a = rating_a + k_factor * (actual_a - expected_a)
    new_rating_b = rating_b + k_factor * (actual_b - expected_b)

    return new_rating_a, new_rating_b


def initialize_ratings(posts_dir: Path, rankings_dir: Path) -> Path:
    """
    Initialize ELO ratings for all posts.

    Creates elo_ratings.parquet with default scores for all posts.

    Args:
        posts_dir: Directory containing blog posts
        rankings_dir: Directory to store ranking data

    Returns:
        Path to elo_ratings.parquet
    """
    rankings_dir.mkdir(parents=True, exist_ok=True)
    ratings_path = rankings_dir / "elo_ratings.parquet"

    # If ratings already exist, don't overwrite
    if ratings_path.exists():
        return ratings_path

    # Find all markdown posts
    post_files = list(posts_dir.glob("*.md"))

    if not post_files:
        raise ValueError(f"No posts found in {posts_dir}")

    # Create initial ratings DataFrame
    data = {
        "post_id": [p.stem for p in post_files],
        "elo_global": [DEFAULT_ELO] * len(post_files),
        "games_played": [0] * len(post_files),
        "last_updated": [datetime.now(timezone.utc)] * len(post_files),
    }

    df = pl.DataFrame(data)
    df.write_parquet(ratings_path)

    return ratings_path


def update_ratings(
    rankings_dir: Path,
    post_a: str,
    post_b: str,
    winner: str
) -> tuple[float, float]:
    """
    Update ELO ratings after a comparison.

    Args:
        rankings_dir: Directory containing ranking data
        post_a: Post ID (filename stem) for post A
        post_b: Post ID (filename stem) for post B
        winner: "A" or "B"

    Returns:
        (new_rating_a, new_rating_b): Updated ELO ratings
    """
    ratings_path = rankings_dir / "elo_ratings.parquet"

    if not ratings_path.exists():
        raise ValueError(f"Ratings file not found: {ratings_path}")

    # Load ratings
    df = pl.read_parquet(ratings_path)

    # Get current ratings
    rating_a_row = df.filter(pl.col("post_id") == post_a)
    rating_b_row = df.filter(pl.col("post_id") == post_b)

    if len(rating_a_row) == 0:
        raise ValueError(f"Post not found in ratings: {post_a}")
    if len(rating_b_row) == 0:
        raise ValueError(f"Post not found in ratings: {post_b}")

    current_a = rating_a_row["elo_global"][0]
    current_b = rating_b_row["elo_global"][0]

    # Calculate new ratings
    new_rating_a, new_rating_b = calculate_elo_update(current_a, current_b, winner)

    # Update DataFrame
    now = datetime.now(timezone.utc)

    df = df.with_columns([
        pl.when(pl.col("post_id") == post_a)
        .then(new_rating_a)
        .otherwise(pl.col("elo_global"))
        .alias("elo_global"),

        pl.when(pl.col("post_id") == post_a)
        .then(pl.col("games_played") + 1)
        .when(pl.col("post_id") == post_b)
        .then(pl.col("games_played") + 1)
        .otherwise(pl.col("games_played"))
        .alias("games_played"),

        pl.when(pl.col("post_id") == post_a)
        .then(now)
        .when(pl.col("post_id") == post_b)
        .then(now)
        .otherwise(pl.col("last_updated"))
        .alias("last_updated"),
    ])

    # Also need to update post_b's rating
    df = df.with_columns([
        pl.when(pl.col("post_id") == post_b)
        .then(new_rating_b)
        .otherwise(pl.col("elo_global"))
        .alias("elo_global"),
    ])

    # Write back
    df.write_parquet(ratings_path)

    return new_rating_a, new_rating_b


def get_posts_to_compare(rankings_dir: Path, strategy: str = "fewest_games") -> tuple[str, str]:
    """
    Select two posts to compare based on strategy.

    Args:
        rankings_dir: Directory containing ranking data
        strategy: Selection strategy (currently only "fewest_games")

    Returns:
        (post_a_id, post_b_id): IDs of posts to compare
    """
    ratings_path = rankings_dir / "elo_ratings.parquet"

    if not ratings_path.exists():
        raise ValueError(f"Ratings file not found: {ratings_path}")

    df = pl.read_parquet(ratings_path)

    if strategy == "fewest_games":
        # Sort by games played (ascending), then randomly
        sorted_df = df.sort("games_played")

        # Take top 2
        if len(sorted_df) < 2:
            raise ValueError("Need at least 2 posts to compare")

        post_a = sorted_df["post_id"][0]
        post_b = sorted_df["post_id"][1]

        return post_a, post_b

    else:
        raise ValueError(f"Unknown strategy: {strategy}")
