from __future__ import annotations

from collections.abc import Awaitable, Sequence
from typing import Protocol

from . import types

__all__ = ["Client", "types"]


class _FilesClient(Protocol):
    def upload(self, *, file: str) -> types.File: ...


class _BatchesClient(Protocol):
    def create(self, *, model: str, src: types.BatchJobSource) -> types.BatchJob: ...

    def create_embeddings(
        self, *, model: str, src: types.EmbeddingsBatchJobSource
    ) -> types.BatchJob: ...

    def get(self, *, name: str) -> types.BatchJob: ...


class _ModelsClient(Protocol):
    def generate_content(
        self,
        *,
        model: str,
        contents: Sequence[types.Content],
        config: types.GenerateContentConfig | None = ...,
    ) -> types.GenerateContentResponse: ...


class _AsyncModelsClient(Protocol):
    def generate_content(
        self,
        *,
        model: str,
        contents: Sequence[types.Content],
        config: types.GenerateContentConfig | None = ...,
    ) -> Awaitable[types.GenerateContentResponse]: ...


class _AioClient(Protocol):
    models: _AsyncModelsClient


class Client:
    files: _FilesClient
    batches: _BatchesClient
    models: _ModelsClient
    aio: _AioClient

    def __init__(self, *args: object, **kwargs: object) -> None: ...

    def close(self) -> None: ...
