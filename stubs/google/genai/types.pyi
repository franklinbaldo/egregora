from __future__ import annotations

from typing import Any, Mapping, Sequence

__all__ = [
    "BatchGenerateResponse",
    "BatchJob",
    "BatchJobDest",
    "BatchJobSource",
    "BatchJobState",
    "Candidate",
    "Content",
    "EmbedContentBatch",
    "EmbedContentConfig",
    "EmbedContentResponse",
    "EmbeddingsBatchJobSource",
    "Embedding",
    "EmbeddingResponse",
    "File",
    "FileData",
    "FunctionCall",
    "FunctionDeclaration",
    "FunctionResponse",
    "GenerateContentConfig",
    "GenerateContentResponse",
    "InlinedRequest",
    "JobError",
    "Part",
    "Schema",
    "Tool",
    "Type",
]


class Type:
    OBJECT: str
    ARRAY: str
    STRING: str
    INTEGER: str


class Schema:
    def __init__(
        self,
        *,
        type: str | None = ...,
        properties: Mapping[str, Schema] | None = ...,
        items: Schema | None = ...,
        description: str | None = ...,
        required: Sequence[str] | None = ...,
        nullable: bool | None = ...,
        enum: Sequence[str] | None = ...,
    ) -> None: ...


class FunctionDeclaration:
    name: str
    description: str | None
    parameters: Schema | None

    def __init__(
        self,
        *,
        name: str,
        description: str | None = ...,
        parameters: Schema | None = ...,
    ) -> None: ...


class Tool:
    function_declarations: Sequence[FunctionDeclaration] | None

    def __init__(
        self,
        *,
        function_declarations: Sequence[FunctionDeclaration] | None = ...,
    ) -> None: ...


class FunctionCall:
    id: str | None
    name: str
    args: Mapping[str, Any] | None


class FunctionResponse:
    id: str | None
    name: str
    response: Mapping[str, Any] | None

    def __init__(
        self,
        *,
        id: str | None = ...,
        name: str,
        response: Mapping[str, Any] | None = ...,
    ) -> None: ...


class FileData:
    file_uri: str | None
    mime_type: str | None

    def __init__(
        self,
        *,
        file_uri: str | None = ...,
        mime_type: str | None = ...,
    ) -> None: ...


class Part:
    text: str | None
    function_call: FunctionCall | None
    function_response: FunctionResponse | None
    file_data: FileData | None

    def __init__(
        self,
        *,
        text: str | None = ...,
        function_call: FunctionCall | None = ...,
        function_response: FunctionResponse | None = ...,
        file_data: FileData | None = ...,
    ) -> None: ...


class Content:
    role: str | None
    parts: Sequence[Part] | None

    def __init__(
        self,
        *,
        role: str | None = ...,
        parts: Sequence[Part] | None = ...,
    ) -> None: ...


class Candidate:
    content: Content | None
    finish_reason: str | None
    function_calls: Sequence[FunctionCall] | None


class GenerateContentResponse:
    candidates: Sequence[Candidate] | None
    text: str | None


class GenerateContentConfig:
    temperature: float | None
    tools: Sequence[Tool] | None

    def __init__(
        self,
        *,
        temperature: float | None = ...,
        tools: Sequence[Tool] | None = ...,
    ) -> None: ...


class InlinedRequest:
    model: str
    contents: Sequence[Content]
    config: GenerateContentConfig | None

    def __init__(
        self,
        *,
        model: str,
        contents: Sequence[Content],
        config: GenerateContentConfig | None = ...,
    ) -> None: ...


class BatchJobSource:
    inlined_requests: Sequence[InlinedRequest]

    def __init__(self, *, inlined_requests: Sequence[InlinedRequest]) -> None: ...


class JobError:
    code: str | None
    message: str | None


class BatchGenerateResponse:
    response: GenerateContentResponse | None
    error: JobError | None


class Embedding:
    values: Sequence[float]


class EmbedContentResponse:
    embedding: Embedding | None


class EmbeddingResponse:
    response: EmbedContentResponse | None
    error: JobError | None


class BatchJobDest:
    inlined_responses: Sequence[BatchGenerateResponse] | None
    inlined_embed_content_responses: Sequence[EmbeddingResponse] | None


class BatchJobState:
    name: str


class BatchJob:
    name: str | None
    dest: BatchJobDest | None
    state: BatchJobState | None
    done: bool
    error: JobError | None


class File:
    def __init__(self, *args: object, **kwargs: object) -> None: ...


class EmbedContentConfig:
    task_type: str | None
    output_dimensionality: int | None

    def __init__(
        self,
        *,
        task_type: str | None = ...,
        output_dimensionality: int | None = ...,
    ) -> None: ...


class EmbedContentBatch:
    contents: Sequence[Content]
    config: EmbedContentConfig | None

    def __init__(
        self,
        *,
        contents: Sequence[Content],
        config: EmbedContentConfig | None = ...,
    ) -> None: ...


class EmbeddingsBatchJobSource:
    inlined_requests: EmbedContentBatch

    def __init__(self, *, inlined_requests: EmbedContentBatch) -> None: ...
