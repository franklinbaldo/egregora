from typing import Any
from pydantic import BaseModel, Field


class AgentVariables(BaseModel):
    defaults: dict[str, Any] = Field(default_factory=dict)
    allowed: list[str] = Field(default_factory=list)


class AgentTools(BaseModel):
    use_profiles: list[str] = Field(default_factory=list)
    allow: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)


class AgentSkills(BaseModel):
    enable: list[str] = Field(default_factory=list)


class AgentConfig(BaseModel):
    """Agent configuration with model, tools, skills, and variables.

    Attributes:
        agent_id: Unique identifier for the agent
        model: Model name to use (e.g., "gemini-2.0-flash-exp")
        seed: Optional random seed for reproducibility. When None, the Gemini API
              uses a random seed internally for non-deterministic behavior.
        ttl: Time-to-live for configuration cache
        variables: Variable defaults and allowlist
        tools: Tool configuration (profiles, allow/deny lists)
        skills: Enabled skills
        env: Environment variables

    """

    agent_id: str
    model: str
    seed: int | None = None
    ttl: str
    variables: AgentVariables
    tools: AgentTools
    skills: AgentSkills
    env: dict[str, Any]


class Tool(BaseModel):
    id: str
    kind: str
    inputs: dict[str, Any]
    contracts: dict[str, Any]
