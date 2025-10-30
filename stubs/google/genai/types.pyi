from __future__ import annotations


from typing import Any, Mapping, Sequence

__all__ = [
    "BatchJob",
    "BatchJobDestination",
    "BatchJobSource",
    "Candidate",
    "Content",
    "EmbedContentBatch",
    "EmbedContentConfig",
    "EmbedContentResponse",
    "Embedding",
    "EmbeddingsBatchJob",
    "EmbeddingsBatchJobSource",
    "File",
    "FileData",
    "FunctionCall",
    "FunctionDeclaration",
    "FunctionResponse",
    "GenerateContentConfig",
    "GenerateContentResponse",
    "InlinedEmbeddingResponse",
    "InlinedRequest",
    "InlinedResponse",
    "JobError",
    "JobState",
    "Part",
    "Schema",
    "Tool",
    "Type",
]


class FunctionDeclaration:
    name: str
    description: str | None
    parameters: Any

    def __init__(self, name: str, *, description: str | None = ..., parameters: Any = ...) -> None: ...


class Tool:
    function_declarations: Sequence[FunctionDeclaration] | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class FunctionCall:
    name: str
    args: Mapping[str, Any]

    def __init__(self, name: str | None = ..., args: Mapping[str, Any] | None = ...) -> None: ...


class FunctionResponse:
    name: str | None
    response: Mapping[str, Any] | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class Part:
    text: str | None
    function_call: FunctionCall | None
    function_response: FunctionResponse | None
    file_data: FileData | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class Content:
    role: str | None
    parts: Sequence[Part] | None

    def __init__(self, *, role: str | None = ..., parts: Sequence[Part] | None = ...) -> None: ...


class GenerateContentConfig:
    tools: Sequence[Tool] | None
    temperature: float | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class Candidate:
    content: Content | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class GenerateContentResponse:
    text: str | None
    candidates: Sequence[Candidate] | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class JobError:
    code: str | None
    message: str | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class File:
    name: str | None
    mime_type: str | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class FileData:
    file_uri: str | None
    mime_type: str | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class JobState:
    name: str

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class BatchJobDestination:
    inlined_responses: Sequence[InlinedResponse] | None
    inlined_embed_content_responses: Sequence[InlinedEmbeddingResponse] | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class BatchJob:
    name: str | None
    state: JobState | None
    dest: BatchJobDestination | None
    error: JobError | None
    done: bool

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class EmbeddingsBatchJob:
    name: str | None
    state: JobState | None
    dest: BatchJobDestination | None
    error: JobError | None
    done: bool

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class InlinedRequest:
    model: str
    contents: Sequence[Content]
    config: GenerateContentConfig | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class BatchJobSource:
    inlined_requests: Sequence[InlinedRequest] | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class EmbedContentConfig:
    task_type: str | None
    output_dimensionality: int | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class EmbedContentBatch:
    contents: Sequence[Content]
    config: EmbedContentConfig | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class EmbeddingsBatchJobSource:
    inlined_requests: EmbedContentBatch | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class Embedding:
    values: Sequence[float]

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class EmbedContentResponse:
    embedding: Embedding | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class InlinedResponse:
    response: GenerateContentResponse | None
    error: JobError | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class InlinedEmbeddingResponse:
    response: EmbedContentResponse | None
    error: JobError | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class Schema:
    type: Type
    items: Schema | None
    properties: Mapping[str, Schema] | None
    required: Sequence[str] | None
    enum: Sequence[str] | None
    description: str | None
    default: Any

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class Type:
    OBJECT: Type
    STRING: Type
    ARRAY: Type
    INTEGER: Type
    NUMBER: Type
    BOOLEAN: Type
