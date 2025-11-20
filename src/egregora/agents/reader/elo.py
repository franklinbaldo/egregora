"""Simple ELO helpers for reader agent rankings."""

from __future__ import annotations

DEFAULT_ELO = 1500.0
K_FACTOR = 32.0


def calculate_elo(rating_a: float, rating_b: float, winner: str) -> tuple[float, float]:
    """Calculate new ELO ratings for two competitors."""

    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1 - expected_a

    score_a = 0.5 if winner == "tie" else (1.0 if winner == "a" else 0.0)
    score_b = 0.5 if winner == "tie" else (1.0 if winner == "b" else 0.0)

    new_a = rating_a + K_FACTOR * (score_a - expected_a)
    new_b = rating_b + K_FACTOR * (score_b - expected_b)
    return new_a, new_b
