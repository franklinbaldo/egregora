"""Agent tool and skill registries.

This module provides registries for managing tools and skills that can be used by
AI agents. Tools define specific capabilities (e.g., write_post, read_profile) while
skills are reusable prompt components that can be injected into agent templates.

The registries handle:
- Loading tool and skill definitions from YAML/text files
- Resolving tool profiles and computing tool sets
- Generating content hashes for versioning and reproducibility
- Validating tool and skill references
"""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


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
            content = tool_file.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            tool_id = data.get("id")
            if tool_id:
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
            return yaml.safe_load(profiles_path.read_text(encoding="utf-8")).get("profiles", {})
        return {}

    def resolve_toolset(self, agent_tools_config) -> set[str]:
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

    def get_agent_hash(self, agent_config, prompt_template: str) -> str:
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


class SkillRegistry:
    """Registry for managing agent skills.

    Skills are reusable prompt components that can be injected into agent templates.
    Each skill is loaded from a text file (Jinja2 or Markdown) in the skills directory.

    Attributes:
        skills_path: Path to the directory containing skill files
        _skills: Dictionary mapping skill IDs to Skill objects

    """

    def __init__(self, egregora_path: Path) -> None:
        """Initialize the skill registry.

        Args:
            egregora_path: Path to the .egregora directory

        """
        self.skills_path = egregora_path / "skills"
        self._skills: dict[str, Skill] = self._load_skills()

    def _load_skills(self) -> dict[str, Skill]:
        """Load all skill definitions from text files.

        Scans the skills directory for files and loads their content. The skill ID
        is derived from the filename (stem without extension).

        Returns:
            Dictionary mapping skill IDs to Skill objects

        """
        skills = {}
        if not self.skills_path.exists():
            return skills
        for skill_file in self.skills_path.iterdir():
            if skill_file.is_file():
                skill_id = skill_file.stem
                content = skill_file.read_text(encoding="utf-8")
                skills[skill_id] = Skill(id=skill_id, content=content)
        return skills

    def get_skillset_hash(self, skill_ids: list[str]) -> str:
        """Get the hash for a set of enabled skills.

        Computes a deterministic SHA256 hash of the skill contents to enable
        versioning and reproducibility. Skills are sorted by ID before hashing.

        Args:
            skill_ids: List of skill IDs to hash

        Returns:
            SHA256 hash of the combined skill contents, or empty string if no skills

        """
        if not skill_ids:
            return ""
        missing_skills = set(skill_ids) - set(self._skills.keys())
        if missing_skills:
            logger.warning("Skills not found in registry: %s", missing_skills)
        hashes = sorted(
            [
                _normalize_and_hash(self._skills[skill_id].content)
                for skill_id in skill_ids
                if skill_id in self._skills
            ]
        )
        combined_hash_input = "".join(hashes)
        return hashlib.sha256(combined_hash_input.encode("utf-8")).hexdigest()

    def get_skill_content(self, skill_id: str) -> str | None:
        """Get the content of a skill by ID.

        Args:
            skill_id: The skill ID to retrieve

        Returns:
            The skill's content as a string, or None if the skill doesn't exist

        """
        return self._skills[skill_id].content if skill_id in self._skills else None
