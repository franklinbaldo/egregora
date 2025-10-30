from __future__ import annotations

from typing import Any, Awaitable, Protocol

from . import types as types

__all__ = ["Client", "types"]


class _ModelsClient(Protocol):
    def generate_content(self, *args: Any, **kwargs: Any) -> Any: ...


class _AsyncModelsClient(Protocol):
    def generate_content(self, *args: Any, **kwargs: Any) -> Awaitable[Any]: ...


class _FilesClient(Protocol):
    def upload(self, *args: Any, **kwargs: Any) -> Any: ...


class _AsyncFilesClient(Protocol):
    def upload(self, *args: Any, **kwargs: Any) -> Awaitable[Any]: ...


class _BatchesClient(Protocol):
    def create(self, *args: Any, **kwargs: Any) -> Any: ...

    def create_embeddings(self, *args: Any, **kwargs: Any) -> Any: ...

    def get(self, *args: Any, **kwargs: Any) -> Any: ...


class _AsyncClient(Protocol):
    models: _AsyncModelsClient
    files: _AsyncFilesClient


class Client:
    models: _ModelsClient
    aio: _AsyncClient
    batches: _BatchesClient
    files: _FilesClient

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
