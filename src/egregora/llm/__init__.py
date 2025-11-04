"""Shared LLM infrastructure for Pydantic AI agents.

This module provides reusable components for all LLM-powered features in Egregora:
- Agent factory functions with standard configuration
- Shared evaluation helpers
- Common utilities for agent development

All LLM interactions should eventually use Pydantic AI through this module.
"""

from egregora.llm.base import create_agent, create_agent_with_result_type

__all__ = ["create_agent", "create_agent_with_result_type"]
