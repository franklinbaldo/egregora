"""Shared utilities and tools for Egregora agents.

This package contains functionality shared across multiple agents (writer, reader, etc.):
- rag: RAG knowledge system (chunking, embedding, storage, retrieval)
- annotations: Conversation annotations
- author_profiles: Author profiling (via knowledge/profiles)

"""

from egregora.agents.shared import annotations, rag

__all__ = ["annotations", "rag"]
