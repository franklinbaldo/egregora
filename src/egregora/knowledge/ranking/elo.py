"""ELO rating system for blog post quality ranking."""

from pathlib import Path

from .store import RankingStore

DEFAULT_ELO = 1500
K_FACTOR = 32
MIN_POSTS_TO_COMPARE = 2


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
    rating_a: float, rating_b: float, winner: str, k_factor: int = K_FACTOR
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


def initialize_ratings(posts_dir: Path, rankings_dir: Path) -> RankingStore:
    """
    Initialize ELO ratings for all posts.

    Creates DuckDB database with default scores for all posts.

    Args:
        posts_dir: Directory containing blog posts
        rankings_dir: Directory to store ranking data

    Returns:
        RankingStore instance
    """
    # Find all markdown posts (including nested directories like .posts)
    post_files = sorted(
        p for p in posts_dir.rglob("*.md") if p.is_file()
    )
    # Find all markdown posts, preferring the hidden .posts directory when present
    search_dirs = []
    hidden_posts_dir = posts_dir / ".posts"
    if hidden_posts_dir.exists():
        search_dirs.append(hidden_posts_dir)
    search_dirs.append(posts_dir)

    seen: set[Path] = set()
    post_files: list[Path] = []
    for directory in search_dirs:
        if not directory.exists():
            continue

        for path in directory.glob("**/*.md"):
            if path.is_file() and path not in seen:
                seen.add(path)
                post_files.append(path)

    if not post_files:
        raise ValueError(f"No posts found in {posts_dir}")

    # Create store
    store = RankingStore(rankings_dir)

    # Initialize ratings for all posts
    post_ids = [p.stem for p in post_files]
    store.initialize_ratings(post_ids)

    return store


def update_ratings(
    rankings_dir: Path, post_a: str, post_b: str, winner: str
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
    store = RankingStore(rankings_dir)

    # Get current ratings
    rating_a_data = store.get_rating(post_a)
    rating_b_data = store.get_rating(post_b)

    if not rating_a_data:
        raise ValueError(f"Post not found in ratings: {post_a}")
    if not rating_b_data:
        raise ValueError(f"Post not found in ratings: {post_b}")

    current_a = rating_a_data["elo_global"]
    current_b = rating_b_data["elo_global"]

    # Calculate new ratings
    new_rating_a, new_rating_b = calculate_elo_update(current_a, current_b, winner)

    # Update in store
    store.update_ratings(post_a, post_b, new_rating_a, new_rating_b)

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
    store = RankingStore(rankings_dir)
    posts = store.get_posts_to_compare(strategy=strategy, n=MIN_POSTS_TO_COMPARE)

    if len(posts) < MIN_POSTS_TO_COMPARE:
        raise ValueError(f"Need at least {MIN_POSTS_TO_COMPARE} posts to compare")

    return posts[0], posts[1]
