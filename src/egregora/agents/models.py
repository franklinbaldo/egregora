from pydantic import BaseModel, Field
from typing import List, Dict, Any

class AgentVariables(BaseModel):
    defaults: Dict[str, Any] = Field(default_factory=dict)
    allowed: List[str] = Field(default_factory=list)

class AgentTools(BaseModel):
    use_profiles: List[str] = Field(default_factory=list)
    allow: List[str] = Field(default_factory=list)
    deny: List[str] = Field(default_factory=list)

class AgentSkills(BaseModel):
    enable: List[str] = Field(default_factory=list)

class AgentConfig(BaseModel):
    agent_id: str
    model: str
    seed: int
    ttl: str
    variables: AgentVariables
    tools: AgentTools
    skills: AgentSkills
    env: Dict[str, Any]

class Tool(BaseModel):
    id: str
    kind: str
    inputs: Dict[str, Any]
    contracts: Dict[str, Any]
