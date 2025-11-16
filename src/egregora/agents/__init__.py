"""Agent systems for Egregora.

This package contains all LLM-powered agent behaviors including
writing and banner generation.

The previous implementation eagerly imported the ``banner`` and ``writer``
submodules at package import time. That caused circular import errors once the
MkDocs adapters started importing ``egregora.agents.shared.author_profiles``
(which implicitly loads ``egregora.agents``).  Lazily resolving these
submodules avoids the circular dependency while keeping the public API
unchanged.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from egregora.agents.registry import AgentResolver, ToolRegistry, load_agent
from egregora.utils.pydantic_ai_retry import install_pydantic_ai_retry_transport

__all__ = ["AgentResolver", "ToolRegistry", "banner", "load_agent", "writer"]


def __getattr__(name: str) -> Any:
    """Lazily import heavy agent modules to avoid circular imports."""
    if name in {"banner", "writer"}:
        module = import_module(f"egregora.agents.{name}")
        globals()[name] = module
        return module
    raise AttributeError(name)


# Ensure pydantic-ai HTTP clients use tenacity transport for retries
install_pydantic_ai_retry_transport()
