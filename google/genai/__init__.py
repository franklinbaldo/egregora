"""Stub google.genai package for test-time imports."""

from pathlib import Path
from types import SimpleNamespace

__path__: list[str] = [str(Path(__file__).resolve().parent)]

from . import types


class _DummyClient:
    def __init__(self, *args, **kwargs):
        empty = SimpleNamespace(candidates=[])
        self.models = SimpleNamespace(generate_content=lambda *a, **k: empty)
        self.aio = SimpleNamespace(models=self.models)
        self.files = SimpleNamespace(
            upload=lambda *a, **k: SimpleNamespace(
                uri="stub://file", mime_type="application/octet-stream"
            )
        )
        dummy_job = SimpleNamespace(
            name="stub-job",
            dest=SimpleNamespace(inlined_responses=[]),
            state=SimpleNamespace(name="JOB_STATE_SUCCEEDED"),
            done=True,
            error=None,
        )
        self.batches = SimpleNamespace(create=lambda *a, **k: dummy_job, get=lambda *a, **k: dummy_job)

    def close(self) -> None:  # pragma: no cover - compatibility shim
        return None


Client = _DummyClient
