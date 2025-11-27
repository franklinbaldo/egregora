"""Shared utilities and tools for Egregora agents.

This package contains functionality shared across multiple agents (writer, reader, etc.):
- annotations: Conversation annotations
- author_profiles: Author profiling (via knowledge/profiles)

Note: RAG functionality has been moved to egregora.rag package.

"""

from egregora.agents.shared import annotations

__all__ = ["annotations"]
