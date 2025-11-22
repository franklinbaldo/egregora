"""ELO math helpers for reader agent evaluations."""

from __future__ import annotations

from typing import Literal

# Standard ELO constants
DEFAULT_ELO = 1500.0
DEFAULT_K_FACTOR = 32


def calculate_expected_score(rating_a: float, rating_b: float) -> float:
    """Probability that player A (post A) wins against player B."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def calculate_elo_update(
    rating_a: float,
    rating_b: float,
    winner: Literal["a", "b", "tie"],
    k_factor: float = DEFAULT_K_FACTOR,
) -> tuple[float, float]:
    """Compute new ELO ratings after a comparison."""
    expected_a = calculate_expected_score(rating_a, rating_b)
    expected_b = calculate_expected_score(rating_b, rating_a)

    if winner == "a":
        score_a, score_b = 1.0, 0.0
    elif winner == "b":
        score_a, score_b = 0.0, 1.0
    else:
        score_a, score_b = 0.5, 0.5

    new_rating_a = rating_a + k_factor * (score_a - expected_a)
    new_rating_b = rating_b + k_factor * (score_b - expected_b)
    return new_rating_a, new_rating_b
