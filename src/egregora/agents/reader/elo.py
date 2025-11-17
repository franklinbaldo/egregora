"""ELO rating system for post quality rankings.

Pure functional implementation of ELO calculations for pairwise comparisons.
Uses standard chess-style ELO with configurable K-factor.
"""

from __future__ import annotations

from typing import Literal

# ELO rating constants
DEFAULT_ELO = 1500.0
K_FACTOR = 32


def calculate_expected_score(rating_a: float, rating_b: float) -> float:
    """Calculate expected score for player A against player B.

    Args:
        rating_a: Current ELO rating of player A
        rating_b: Current ELO rating of player B

    Returns:
        Expected score (probability) between 0 and 1

    """
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def calculate_elo_update(
    rating_a: float,
    rating_b: float,
    winner: Literal["a", "b", "tie"],
    k_factor: float = K_FACTOR,
) -> tuple[float, float]:
    """Calculate new ELO ratings after a comparison.

    Args:
        rating_a: Current ELO rating of post A
        rating_b: Current ELO rating of post B
        winner: Which post won ("a", "b", or "tie")
        k_factor: K-factor controlling rating volatility (default: 32)

    Returns:
        Tuple of (new_rating_a, new_rating_b)

    Examples:
        >>> calculate_elo_update(1500.0, 1500.0, "a")
        (1516.0, 1484.0)
        >>> calculate_elo_update(1500.0, 1500.0, "tie")
        (1500.0, 1500.0)

    """
    # Calculate expected scores
    expected_a = calculate_expected_score(rating_a, rating_b)
    expected_b = calculate_expected_score(rating_b, rating_a)

    # Determine actual scores
    if winner == "a":
        actual_a, actual_b = 1.0, 0.0
    elif winner == "b":
        actual_a, actual_b = 0.0, 1.0
    else:  # tie
        actual_a, actual_b = 0.5, 0.5

    # Calculate rating updates
    new_rating_a = rating_a + k_factor * (actual_a - expected_a)
    new_rating_b = rating_b + k_factor * (actual_b - expected_b)

    return new_rating_a, new_rating_b
