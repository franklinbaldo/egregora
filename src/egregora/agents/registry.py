import hashlib
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

@dataclass
class Tool:
    id: str
    kind: str
    inputs: Dict[str, Any]
    contracts: Dict[str, Any]
    content: str  # The raw YAML content for hashing

@dataclass
class Skill:
    id: str
    content: str

def _normalize_and_hash(content: str) -> str:
    """Normalize YAML content and return its SHA256 hash."""
    # A more robust implementation would deeply sort keys
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

class ToolRegistry:
    def __init__(self, egregora_path: Path):
        self.tools_path = egregora_path / "tools"
        self._tools: Dict[str, Tool] = self._load_tools()
        self._profiles: Dict[str, Any] = self._load_profiles()

    def _load_tools(self) -> Dict[str, Tool]:
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
                    content=content
                )
        return tools

    def _load_profiles(self) -> Dict[str, Any]:
        profiles_path = self.tools_path / "profiles.yaml"
        if profiles_path.exists():
            return yaml.safe_load(profiles_path.read_text(encoding="utf-8")).get("profiles", {})
        return {}

    def resolve_toolset(self, agent_tools_config) -> Set[str]:
        """Resolve the final set of tool IDs for an agent."""
        toolset = set()

        # Apply profiles first
        for profile_name in agent_tools_config.use_profiles:
            profile = self._profiles.get(profile_name, {})
            toolset.update(profile.get("allow", []))
            toolset.difference_update(profile.get("deny", []))

        # Apply agent-specific allow/deny
        toolset.update(agent_tools_config.allow)
        toolset.difference_update(agent_tools_config.deny)

        return toolset

    def get_toolset_hash(self, tool_ids: Set[str]) -> str:
        """Get the hash for a set of enabled tools."""
        if not tool_ids:
            return ""

        hashes = sorted([_normalize_and_hash(self._tools[tool_id].content) for tool_id in tool_ids if tool_id in self._tools])
        combined_hash_input = "".join(hashes)
        return hashlib.sha256(combined_hash_input.encode('utf-8')).hexdigest()

    def get_agent_hash(self, agent_config, prompt_template: str) -> str:
        """Get the hash for an agent's configuration."""
        # A more robust implementation would deeply sort keys
        front_matter_str = yaml.dump(
            agent_config.dict(),
            sort_keys=True,
        )
        return hashlib.sha256(
            (front_matter_str + prompt_template).encode("utf-8")
        ).hexdigest()


class SkillRegistry:
    def __init__(self, egregora_path: Path):
        self.skills_path = egregora_path / "skills"
        self._skills: Dict[str, Skill] = self._load_skills()

    def _load_skills(self) -> Dict[str, Skill]:
        skills = {}
        for skill_file in self.skills_path.iterdir():
            if skill_file.is_file():
                skill_id = skill_file.stem
                content = skill_file.read_text(encoding="utf-8")
                skills[skill_id] = Skill(id=skill_id, content=content)
        return skills

    def get_skillset_hash(self, skill_ids: List[str]) -> str:
        """Get the hash for a set of enabled skills."""
        if not skill_ids:
            return ""

        hashes = sorted([_normalize_and_hash(self._skills[skill_id].content) for skill_id in skill_ids if skill_id in self._skills])
        combined_hash_input = "".join(hashes)
        return hashlib.sha256(combined_hash_input.encode('utf-8')).hexdigest()

    def get_skill_content(self, skill_id: str) -> str | None:
        return self._skills[skill_id].content if skill_id in self._skills else None
