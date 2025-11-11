"""Egregora Ranking Agent - LLM-powered ELO ranking system for blog posts.

Three-turn conversation protocol with profile impersonation for diverse perspectives.
Uses DuckDB for fast ELO rating updates and comment storage.

Documentation:
- Ranking Feature: docs/features/ranking.md
- API Reference: docs/reference/api.md#ranking-system
- CLI Reference: docs/reference/cli.md#egregora-rank
"""

from egregora.agents.ranking.agent import run_comparison_with_pydantic_agent as run_comparison
from egregora.agents.ranking.elo import calculate_elo_update, initialize_ratings, update_ratings
from egregora.agents.ranking.store import RankingStore

__all__ = [
    "RankingStore",
    "calculate_elo_update",
    "initialize_ratings",
    "run_comparison",
    "update_ratings",
]
