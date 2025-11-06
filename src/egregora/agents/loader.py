"""Agent configuration loader.

This module provides utilities for loading agent configurations from Jinja2 template
files with YAML frontmatter. Agent configurations define model settings, tools, skills,
and prompt templates for AI agents in the Egregora system.
"""

import re
from pathlib import Path

import yaml

from egregora.agents.models import AgentConfig


def load_agent(agent_name: str, egregora_path: Path) -> tuple[AgentConfig, str]:
    """Load an agent's configuration from a .jinja file.

    Reads an agent configuration file in Jinja2 format with YAML frontmatter embedded
    in Jinja comments. The frontmatter is parsed and validated against the AgentConfig
    Pydantic model, while the rest of the file becomes the prompt template.

    Args:
        agent_name: Name of the agent (without .jinja extension, e.g., "writer", "editor")
        egregora_path: Path to the .egregora directory containing agent configurations

    Returns:
        A tuple of (AgentConfig, prompt_template) where:
            - AgentConfig: Validated configuration object with model, tools, skills, etc.
            - prompt_template: The Jinja2 template string for the agent's system prompt

    Raises:
        FileNotFoundError: If the agent template file doesn't exist
        ValueError: If the YAML frontmatter is invalid or missing
        ValueError: If the agent configuration fails Pydantic validation

    Example:
        >>> config, template = load_agent("writer", Path(".egregora"))
        >>> print(config.model)
        'gemini-2.0-flash-exp'
        >>> print(config.agent_id)
        'writer_v1'

    """
    agent_path = egregora_path / "agents" / f"{agent_name}.jinja"
    if not agent_path.exists():
        msg = f"Agent template not found: {agent_path}"
        raise FileNotFoundError(msg)
    raw_content = agent_path.read_text(encoding="utf-8")
    match = re.search("{#---(.*?)#---#}", raw_content, re.DOTALL)
    if not match:
        msg = f"Front-matter not found in {agent_path}"
        raise ValueError(msg)
    front_matter_str = match.group(1)
    prompt_template = raw_content[match.end() :].strip()
    try:
        config_dict = yaml.safe_load(front_matter_str)
    except yaml.YAMLError as e:
        msg = f"Invalid YAML in {agent_path}: {e}"
        raise ValueError(msg) from e
    try:
        agent_config = AgentConfig(**config_dict)
    except Exception as e:
        msg = f"Invalid agent config in {agent_path}: {e}"
        raise ValueError(msg) from e
    return (agent_config, prompt_template)
