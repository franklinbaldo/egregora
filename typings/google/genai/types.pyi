from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass
class Part:
    text: str | None = None
    file_data: FileData | None = None


@dataclass
class FileData:
    file_uri: str | None = None
    mime_type: str | None = None


@dataclass
class Content:
    role: str | None = None
    parts: Sequence[Part] | None = None


@dataclass
class GenerateContentConfig:
    temperature: float | None = None


@dataclass
class GenerateContentResponse:
    text: str | None = None


@dataclass
class JobError:
    code: str | None = None
    message: str | None = None


@dataclass
class File:
    name: str | None = None
    uri: str | None = None
    mime_type: str | None = None


@dataclass
class InlinedRequest:
    model: str
    contents: Sequence[Content]
    config: GenerateContentConfig | None = None


@dataclass
class InlinedResponse:
    response: GenerateContentResponse | None = None
    error: JobError | None = None


@dataclass
class BatchJobDest:
    inlined_responses: Sequence[InlinedResponse] | None = None


@dataclass
class BatchJob:
    name: str | None = None
    dest: BatchJobDest | None = None


@dataclass
class BatchJobSource:
    inlined_requests: Sequence[InlinedRequest]


@dataclass
class EmbeddingsBatchJobSource:
    inlined_requests: EmbedContentBatch


@dataclass
class EmbedContentConfig:
    task_type: str | None = None
    output_dimensionality: int | None = None


@dataclass
class EmbedContentBatch:
    contents: Sequence[Content]
    config: EmbedContentConfig | None = None


@dataclass
class EmbeddingsBatchJob:
    name: str | None = None


@dataclass
class EmbeddingsBatchJobDest:
    batch: EmbeddingsBatchJob | None = None


@dataclass
class EmbeddingsBatchJobResponse:
    embeddings: Sequence[Sequence[float]] | None = None

