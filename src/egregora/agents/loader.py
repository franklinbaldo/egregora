from dataclasses import dataclass, field
from pathlib import Path
import frontmatter
import yaml
import re

@dataclass
class AgentConfig:
    agent_id: str
    model: str
    seed: int
    ttl: str
    variables: dict
    tools: dict
    skills: dict
    env: dict
    prompt_template: str

def load_agent(agent_name: str, egregora_path: Path) -> AgentConfig:
    """Loads an agent's configuration from a .jinja file."""
    agent_path = egregora_path / "agents" / f"{agent_name}.jinja"

    if not agent_path.exists():
        raise FileNotFoundError(f"Agent template not found: {agent_path}")

    raw_content = agent_path.read_text(encoding="utf-8")

    # Extract front-matter from within Jinja comment
    match = re.search(r"{#---(.*?)#---#}", raw_content, re.DOTALL)
    if not match:
        raise ValueError(f"Front-matter not found in {agent_path}")

    front_matter_str = match.group(1)

    # The rest of the file is the prompt template
    prompt_template = raw_content[match.end():].strip()

    # Parse the YAML front-matter
    config_dict = yaml.safe_load(front_matter_str)

    return AgentConfig(
        agent_id=config_dict.get("agent_id"),
        model=config_dict.get("model"),
        seed=config_dict.get("seed"),
        ttl=config_dict.get("ttl"),
        variables=config_dict.get("variables"),
        tools=config_dict.get("tools"),
        skills=config_dict.get("skills"),
        env=config_dict.get("env"),
        prompt_template=prompt_template,
    )
