from __future__ import annotations

from typing import Any, Protocol, Sequence

from . import types


class _FilesClient(Protocol):
    def upload(self, *, file: Any) -> types.File: ...


class _ModelsClient(Protocol):
    def generate_content(
        self,
        contents: Sequence[types.Content],
        *,
        model: str,
        config: types.GenerateContentConfig | None = ...,
    ) -> types.GenerateContentResponse: ...


class _BatchesClient(Protocol):
    def create(
        self,
        *,
        model: str,
        src: types.BatchJobSource,
    ) -> types.BatchJob: ...


class Client(Protocol):
    files: _FilesClient
    models: _ModelsClient
    batches: _BatchesClient


__all__ = ["Client", "types"]

