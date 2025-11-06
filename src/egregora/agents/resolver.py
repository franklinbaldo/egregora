import logging
from pathlib import Path
from typing import Any

import frontmatter

from egregora.agents.loader import load_agent
from egregora.agents.models import AgentConfig

logger = logging.getLogger(__name__)


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
    """Merges variables from the post's front-matter into the agent's variables,

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
