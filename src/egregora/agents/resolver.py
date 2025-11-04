import frontmatter
from pathlib import Path
from typing import Any, Dict
from .loader import AgentConfig, load_agent

def resolve_agent_name(post_path: Path, docs_path: Path) -> str:
    """
    Resolves the agent name based on post, section, and default fallbacks.
    """
    # 1. Check for agent in post's front-matter
    post = frontmatter.load(post_path)
    if "egregora" in post and "agent" in post["egregora"]:
        return post["egregora"]["agent"]

    # 2. Check for agent in section's _agent.md
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

    # 3. Fallback to default agent
    return "_default"

def merge_variables(agent_config: AgentConfig, post_path: Path) -> Dict[str, Any]:
    """
    Merges variables from the post's front-matter into the agent's variables,
    respecting the allowlist.
    """
    post = frontmatter.load(post_path)
    post_vars = post.get("egregora", {}).get("variables", {})

    merged_vars = agent_config.variables.get("defaults", {}).copy()
    allowed_vars = agent_config.variables.get("allowed", [])

    for key, value in post_vars.items():
        if key in allowed_vars:
            merged_vars[key] = value
        else:
            print(f"Warning: Variable '{key}' from {post_path.name} is not allowed by the agent and will be ignored.")

    return merged_vars

class AgentResolver:
    def __init__(self, egregora_path: Path, docs_path: Path):
        self.egregora_path = egregora_path
        self.docs_path = docs_path

    def resolve(self, post_path: Path, agent_override: str | None = None) -> tuple[AgentConfig, Dict[str, Any]]:
        """
        Resolves the agent for a given post and returns the agent config
        and the final merged variables.
        """
        agent_name = agent_override or resolve_agent_name(post_path, self.docs_path)
        agent_config = load_agent(agent_name, self.egregora_path)
        final_vars = merge_variables(agent_config, post_path)
        return agent_config, final_vars
