import re
from pathlib import Path

import yaml

from .models import AgentConfig


def load_agent(agent_name: str, egregora_path: Path) -> tuple[AgentConfig, str]:
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
    prompt_template = raw_content[match.end() :].strip()

    # Parse the YAML front-matter and validate with Pydantic
    config_dict = yaml.safe_load(front_matter_str)
    agent_config = AgentConfig(**config_dict)

    return agent_config, prompt_template
