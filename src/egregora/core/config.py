from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field
import yaml


class LLMConfig(BaseModel):
    model: str = "models/gemini-2.5-flash"
    api_key: str | None = None
    temperature: float = 0.7
    max_retries: int = 3


class CuratorConfig(BaseModel):
    enabled: bool = True
    min_message_length: int = 15
    cluster_threshold: float = 0.7
    max_topics_per_day: int = 10


class EnricherConfig(BaseModel):
    enabled: bool = True
    max_enrichments_per_post: int = 5
    enable_rag: bool = False
    enable_web: bool = False


class WriterConfig(BaseModel):
    enabled: bool = True
    language: str = "pt-BR"
    max_post_length: int = 5000


class ProfilerConfig(BaseModel):
    enabled: bool = False
    min_messages: int = 10


class PipelineConfig(BaseModel):
    input_dir: Path
    output_dir: Path
    llm: LLMConfig = Field(default_factory=LLMConfig)
    curator: CuratorConfig = Field(default_factory=CuratorConfig)
    enricher: EnricherConfig = Field(default_factory=EnricherConfig)
    writer: WriterConfig = Field(default_factory=WriterConfig)
    profiler: ProfilerConfig = Field(default_factory=ProfilerConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "PipelineConfig":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self, path: Path):
        with open(path, "w") as f:
            yaml.safe_dump(self.model_dump(), f, default_flow_style=False)
