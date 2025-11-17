"""Reader agent for post quality evaluation and feedback.

The reader agent simulates human readers evaluating blog posts through:
- Pairwise post comparisons
- Structured feedback (comments + star ratings)
- ELO-based quality rankings

This module provides:
- compare_posts: Main agent function for post evaluation
- ELO calculation utilities (from agents/reader/elo.py)
- Rating persistence via EloStore (from database/elo_store.py)
- Data models for feedback and comparisons (from agents/reader/models.py)
"""

from egregora.agents.reader.agent import compare_posts
from egregora.agents.reader.elo import DEFAULT_ELO, K_FACTOR, calculate_elo_update
from egregora.agents.reader.models import (
    EvaluationRequest,
    PostComparison,
    RankingResult,
    ReaderFeedback,
)
from egregora.database.elo_store import EloRating, EloStore

__all__ = [
    # Agent
    "compare_posts",
    # ELO calculations
    "calculate_elo_update",
    "DEFAULT_ELO",
    "K_FACTOR",
    # Persistence
    "EloStore",
    "EloRating",
    # Data models
    "ReaderFeedback",
    "PostComparison",
    "EvaluationRequest",
    "RankingResult",
]
