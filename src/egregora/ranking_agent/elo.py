"""ELO rating system for blog posts."""

import polars as pl
from pathlib import Path
import random

DEFAULT_ELO = 1500
K_FACTOR = 32

def init_ratings(posts_dir: Path, ratings_path: Path) -> pl.DataFrame:
    """Initializes the ELO ratings file if it doesn't exist."""
    if ratings_path.exists():
        return pl.read_parquet(ratings_path)

    posts = [p.name for p in posts_dir.glob("*.md")]
    df = pl.DataFrame({
        "post": posts,
        "rating": [DEFAULT_ELO] * len(posts),
        "games": [0] * len(posts),
    })
    df.write_parquet(ratings_path)
    return df

def update_ratings(ratings_df: pl.DataFrame, winner: str, loser: str) -> pl.DataFrame:
    """Updates the ELO ratings based on the winner and loser."""
    winner_row = ratings_df.filter(pl.col("post") == winner)
    loser_row = ratings_df.filter(pl.col("post") == loser)

    winner_rating = winner_row["rating"][0]
    loser_rating = loser_row["rating"][0]

    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner_rating - loser_rating) / 400))

    new_winner_rating = winner_rating + K_FACTOR * (1 - expected_winner)
    new_loser_rating = loser_rating + K_FACTOR * (0 - expected_loser)

    ratings_df = ratings_df.with_columns(
        pl.when(pl.col("post") == winner)
        .then(new_winner_rating)
        .otherwise(pl.col("rating"))
        .alias("rating")
    )
    ratings_df = ratings_df.with_columns(
        pl.when(pl.col("post") == loser)
        .then(new_loser_rating)
        .otherwise(pl.col("rating"))
        .alias("rating")
    )

    # Increment games played
    ratings_df = ratings_df.with_columns(
        pl.when((pl.col("post") == winner) | (pl.col("post") == loser))
        .then(pl.col("games") + 1)
        .otherwise(pl.col("games"))
        .alias("games")
    )

    return ratings_df

def select_posts_to_rate(ratings_df: pl.DataFrame) -> tuple[str, str]:
    """Selects two posts to rate, prioritizing those with fewer games."""
    min_games = ratings_df["games"].min()
    candidates = ratings_df.filter(pl.col("games") == min_games)

    if len(candidates) < 2:
        # If not enough candidates at min_games, just take the two with the least games
        candidates = ratings_df.sort("games").head(2)

    return tuple(candidates["post"].sample(n=2, with_replacement=False).to_list())
