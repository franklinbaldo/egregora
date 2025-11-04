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
    agent_id: str
    model: str
    seed: int
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


class FinishResult(BaseModel):
    decision: str
    notes: str
