from __future__ import annotations

from typing import Any, Iterable, Sequence

class Type:
    OBJECT: str
    STRING: str
    ARRAY: str
    INTEGER: str

class Schema:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class FunctionDeclaration:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class Tool:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class File:
    name: str | None

class FileData:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class Part:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    text: str | None
    function_call: Any
    function_response: Any

class Content:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    parts: list[Part] | None
    role: str | None

class FunctionResponse:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    name: str
    response: Any

class FunctionCall:
    name: str
    args: dict[str, Any] | None
    id: str | None

class Candidate:
    content: Content | None

class GenerateContentResponse:
    candidates: Sequence[Candidate] | None

class GenerateContentConfig:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    tools: Sequence[Tool] | None

class JobError(Exception):
    code: str | None
    message: str | None

class BatchJob:
    name: str | None
    dest: Any

class BatchJobSource:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class InlinedRequest:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class EmbeddingsBatchJobSource:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    inlined_requests: Any

class EmbedContentBatch:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class EmbedContentConfig:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class Embedding:
    values: Sequence[float]

class EmbedContentResponse:
    embedding: Embedding | None

__all__ = [
    "Type",
    "Schema",
    "FunctionDeclaration",
    "Tool",
    "File",
    "FileData",
    "Part",
    "Content",
    "FunctionResponse",
    "FunctionCall",
    "Candidate",
    "GenerateContentResponse",
    "GenerateContentConfig",
    "JobError",
    "BatchJob",
    "BatchJobSource",
    "InlinedRequest",
    "EmbeddingsBatchJobSource",
    "EmbedContentBatch",
    "EmbedContentConfig",
    "Embedding",
    "EmbedContentResponse",
]
