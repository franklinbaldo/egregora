from dataclasses import dataclass
from typing import Any


@dataclass
class BatchPromptRequest:
    tag: str
    prompt: Any = None


@dataclass
class BatchPromptResult:
    tag: str
    response: Any = None
    error: Exception | None = None


@dataclass
class EmbeddingBatchRequest:
    tag: str
    text: str


@dataclass
class EmbeddingBatchResult:
    tag: str
    embedding: list[float] | None = None
    error: Exception | None = None
