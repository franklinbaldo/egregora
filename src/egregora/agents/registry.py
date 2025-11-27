"""Agent configuration, tool, and skill registries.

This module provides registries and utilities for managing AI agent configurations,
tools, and skills. It handles:
- Loading agent configurations from Jinja2 templates with YAML frontmatter
- Resolving agent names from post metadata and directory structure
- Merging agent variables with post-specific overrides
- Managing tool definitions and tool profiles
- Managing reusable skill components
- Generating content hashes for versioning and reproducibility
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import frontmatter
import yaml

from egregora.agents.models import AgentConfig

if TYPE_CHECKING:
    from egregora.agents.models import AgentTools

logger = logging.getLogger(__name__)


class ToolRegistryError(Exception):
    """Raised when tool definitions or profiles cannot be loaded."""


@dataclass
class Tool:
    id: str
    kind: str
    inputs: dict[str, Any]
    contracts: dict[str, Any]
    content: str


@dataclass
class Skill:
    id: str
    content: str


def _normalize_and_hash(content: str) -> str:
    """Normalize YAML content and return its SHA256 hash."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# Agent configuration loading (from loader.py)


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


# Agent resolution and variable merging (from resolver.py)


def resolve_agent_name(post_path: Path, docs_path: Path) -> str:
    """Resolves the agent name based on post, section, and default fallbacks."""
    post = frontmatter.load(post_path)
    if "egregora" in post and "agent" in post["egregora"]:
        return post["egregora"]["agent"]
    current_dir = post_path.parent
    while current_dir != docs_path.parent:
        agent_md_path = current_dir / "_agent.md"
        if agent_md_path.exists():
            agent_md = frontmatter.load(agent_md_path)
            if "egregora" in agent_md and "agent" in agent_md["egregora"]:
                return agent_md["egregora"]["agent"]
        if current_dir == docs_path:
            break
        current_dir = current_dir.parent
    return "_default"


def merge_variables(agent_config: AgentConfig, post_path: Path) -> dict[str, Any]:
    """Merges variables from the post's front-matter into the agent's variables,.

    respecting the allowlist.
    """
    post = frontmatter.load(post_path)
    post_vars = post.get("egregora", {}).get("variables", {})
    merged_vars = agent_config.variables.defaults.copy()
    allowed_vars = agent_config.variables.allowed
    for key, value in post_vars.items():
        if key in allowed_vars:
            merged_vars[key] = value
        else:
            logger.warning(
                "Variable '%s' from %s not allowed by agent %s, ignoring",
                key,
                post_path.name,
                agent_config.agent_id,
            )
    return merged_vars


class AgentResolver:
    """Resolver for loading agents and merging configurations.

    Handles resolving which agent to use for a given post based on frontmatter
    metadata and directory structure, then loads and merges configurations.
    """

    def __init__(self, egregora_path: Path, docs_path: Path) -> None:
        self.egregora_path = egregora_path
        self.docs_path = docs_path

    def resolve(
        self, post_path: Path, agent_override: str | None = None
    ) -> tuple[AgentConfig, str, dict[str, Any]]:
        """Resolves the agent for a given post and returns the agent config, prompt template.

        And the final merged variables.
        """
        agent_name = agent_override or resolve_agent_name(post_path, self.docs_path)
        agent_config, prompt_template = load_agent(agent_name, self.egregora_path)
        final_vars = merge_variables(agent_config, post_path)
        return (agent_config, prompt_template, final_vars)


# Tool and skill registries


class ToolRegistry:
    """Registry for managing agent tools and tool profiles.

    The ToolRegistry loads tool definitions from YAML files and manages tool profiles
    that define preset tool configurations. It provides methods to resolve which tools
    an agent can access based on profiles and allow/deny lists.

    Attributes:
        tools_path: Path to the directory containing tool YAML files
        _tools: Dictionary mapping tool IDs to Tool objects
        _profiles: Dictionary mapping profile names to profile configurations

    """

    def __init__(self, egregora_path: Path) -> None:
        """Initialize the tool registry.

        Args:
            egregora_path: Path to the .egregora directory

        """
        self.tools_path = egregora_path / "tools"
        self._tools: dict[str, Tool] = self._load_tools()
        self._profiles: dict[str, Any] = self._load_profiles()

    def _load_tools(self) -> dict[str, Tool]:
        """Load all tool definitions from YAML files.

        Scans the tools directory for .yaml files (excluding profiles.yaml) and
        loads each tool's definition into the registry.

        Returns:
            Dictionary mapping tool IDs to Tool objects

        """
        tools = {}
        for tool_file in self.tools_path.glob("*.yaml"):
            if tool_file.name == "profiles.yaml":
                continue
            try:
                content = tool_file.read_text(encoding="utf-8")
            except OSError as exc:
                msg = f"Failed to read tool definition from {tool_file}"
                raise ToolRegistryError(msg) from exc
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError as exc:
                msg = f"Invalid YAML in tool definition {tool_file}"
                raise ToolRegistryError(msg) from exc
            if not isinstance(data, dict):
                msg = f"Tool definition in {tool_file} must be a mapping, got {type(data).__name__}"
                raise ToolRegistryError(msg)

            tool_id = data.get("id")
            if not tool_id:
                msg = f"Tool definition in {tool_file} missing required 'id' field"
                raise ToolRegistryError(msg)

            tools[tool_id] = Tool(
                id=tool_id,
                kind=data.get("kind"),
                inputs=data.get("inputs"),
                contracts=data.get("contracts"),
                content=content,
            )
        return tools

    def _load_profiles(self) -> dict[str, Any]:
        """Load tool profiles from profiles.yaml.

        Tool profiles define preset configurations of tools with allow/deny lists
        and optional quotas.

        Returns:
            Dictionary mapping profile names to profile configurations

        """
        profiles_path = self.tools_path / "profiles.yaml"
        if profiles_path.exists():
            try:
                content = profiles_path.read_text(encoding="utf-8")
            except OSError as exc:
                msg = f"Failed to read tool profiles from {profiles_path}"
                raise ToolRegistryError(msg) from exc
            try:
                data = yaml.safe_load(content) or {}
            except yaml.YAMLError as exc:
                msg = f"Invalid YAML in tool profiles file {profiles_path}"
                raise ToolRegistryError(msg) from exc
            if not isinstance(data, dict):
                msg = f"Tool profiles in {profiles_path} must be a mapping, got {type(data).__name__}"
                raise ToolRegistryError(msg)
            profiles = data.get("profiles", {})
            if not isinstance(profiles, dict):
                msg = f"'profiles' section in {profiles_path} must be a mapping, got {type(profiles).__name__}"
                raise ToolRegistryError(msg)
            validated_profiles: dict[str, Any] = {}
            for name, profile in profiles.items():
                if not isinstance(profile, dict):
                    msg = f"Profile '{name}' in {profiles_path} must be a mapping, got {type(profile).__name__}"
                    raise ToolRegistryError(msg)

                allow = profile.get("allow", []) or []
                deny = profile.get("deny", []) or []

                if not isinstance(allow, (list, tuple)):
                    msg = (
                        f"'allow' list for profile '{name}' in {profiles_path} must be a sequence of strings, "
                        f"got {type(allow).__name__}"
                    )
                    raise ToolRegistryError(msg)
                if not isinstance(deny, (list, tuple)):
                    msg = (
                        f"'deny' list for profile '{name}' in {profiles_path} must be a sequence of strings, "
                        f"got {type(deny).__name__}"
                    )
                    raise ToolRegistryError(msg)
                if not all(isinstance(item, str) for item in allow):
                    msg = f"All entries in 'allow' for profile '{name}' in {profiles_path} must be strings"
                    raise ToolRegistryError(msg)
                if not all(isinstance(item, str) for item in deny):
                    msg = f"All entries in 'deny' for profile '{name}' in {profiles_path} must be strings"
                    raise ToolRegistryError(msg)

                normalized_profile = dict(profile)
                normalized_profile["allow"] = list(allow)
                normalized_profile["deny"] = list(deny)
                validated_profiles[name] = normalized_profile

            return validated_profiles
        return {}

    def resolve_toolset(self, agent_tools_config: AgentTools) -> set[str]:
        """Resolve the final set of tool IDs for an agent.

        Combines tools from profiles with agent-specific allow/deny lists to determine
        which tools the agent can access. Profiles are applied first, then agent-specific
        rules override.

        Args:
            agent_tools_config: AgentTools configuration with use_profiles, allow, and deny lists

        Returns:
            Set of tool IDs that the agent is allowed to use

        """
        toolset = set()
        for profile_name in agent_tools_config.use_profiles:
            profile = self._profiles.get(profile_name, {})
            toolset.update(profile.get("allow", []))
            toolset.difference_update(profile.get("deny", []))
        toolset.update(agent_tools_config.allow)
        toolset.difference_update(agent_tools_config.deny)
        return toolset

    def get_toolset_hash(self, tool_ids: set[str]) -> str:
        """Get the hash for a set of enabled tools.

        Computes a deterministic SHA256 hash of the tool configurations to enable
        versioning and reproducibility. Tools are sorted by ID before hashing to
        ensure consistent results.

        Args:
            tool_ids: Set of tool IDs to hash

        Returns:
            SHA256 hash of the combined tool configurations, or empty string if no tools

        """
        if not tool_ids:
            return ""
        missing_tools = tool_ids - set(self._tools.keys())
        if missing_tools:
            logger.warning("Tools not found in registry: %s", missing_tools)
        hashes = sorted(
            [
                _normalize_and_hash(self._tools[tool_id].content)
                for tool_id in tool_ids
                if tool_id in self._tools
            ]
        )
        combined_hash_input = "".join(hashes)
        return hashlib.sha256(combined_hash_input.encode("utf-8")).hexdigest()

    def get_agent_hash(self, agent_config: AgentConfig, prompt_template: str) -> str:
        """Get the hash for an agent's configuration.

        Computes a deterministic SHA256 hash of the agent's full configuration,
        including frontmatter and prompt template, for versioning and reproducibility.

        Args:
            agent_config: AgentConfig object with model, tools, skills, etc.
            prompt_template: The Jinja2 template string for the agent's prompt

        Returns:
            SHA256 hash of the agent configuration and template

        """
        front_matter_str = yaml.dump(agent_config.dict(), sort_keys=True)
        return hashlib.sha256((front_matter_str + prompt_template).encode("utf-8")).hexdigest()
