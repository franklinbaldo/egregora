"""Test harness shims to smooth optional third-party dependencies."""

from __future__ import annotations

import sys
import types


def _ensure_google_stub() -> None:
    """Guarantee ``google.genai.types`` exposes the attributes used in tests."""

    existing = sys.modules.get("google.genai.types")
    if existing is not None and hasattr(existing, "FunctionCall"):
        return

    google_module = sys.modules.get("google") or types.ModuleType("google")
    genai_module = getattr(google_module, "genai", None) or types.ModuleType("google.genai")

    google_module.__path__ = getattr(google_module, "__path__", [])
    genai_module.__path__ = getattr(genai_module, "__path__", [])
    genai_types_module = types.ModuleType("google.genai.types")

    class _SimpleStruct:
        def __init__(self, *args, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class _DummyType:
        OBJECT = "object"
        STRING = "string"
        ARRAY = "array"
        INTEGER = "integer"

    class _DummyClient:
        def __init__(self, *args, **kwargs):
            empty = types.SimpleNamespace(candidates=[])
            self.models = types.SimpleNamespace(generate_content=lambda *a, **k: empty)
            self.aio = types.SimpleNamespace(models=self.models)
            self.files = types.SimpleNamespace(
                upload=lambda *a, **k: types.SimpleNamespace(
                    uri="stub://file", mime_type="application/octet-stream"
                )
            )
            dummy_job = types.SimpleNamespace(
                name="stub-job",
                dest=types.SimpleNamespace(inlined_responses=[]),
                state=types.SimpleNamespace(name="JOB_STATE_SUCCEEDED"),
                done=True,
                error=None,
            )
            self.batches = types.SimpleNamespace(
                create=lambda *a, **k: dummy_job, get=lambda *a, **k: dummy_job
            )

        def close(self) -> None:  # pragma: no cover - compatibility shim
            return None

    class _FallbackFunctionCall(_SimpleStruct):
        id: str | None = None
        name: str | None = None

    for attr in (
        "Schema",
        "FunctionDeclaration",
        "Tool",
        "FunctionResponse",
        "Part",
        "Content",
        "GenerateContentConfig",
        "BatchJobSource",
        "CreateBatchJobConfig",
        "InlinedRequest",
        "EmbeddingsBatchJobSource",
        "EmbedContentBatch",
        "EmbedContentConfig",
        "FileData",
        "BatchJob",
        "JobError",
        "FunctionCall",
    ):
        setattr(genai_types_module, attr, _SimpleStruct)

    genai_types_module.FunctionCall = _FallbackFunctionCall
    genai_types_module.Type = _DummyType

    google_module.genai = genai_module
    genai_module.types = genai_types_module
    if not hasattr(genai_module, "Client"):
        genai_module.Client = _DummyClient

    sys.modules["google"] = google_module
    sys.modules["google.genai"] = genai_module
    sys.modules["google.genai.types"] = genai_types_module


_ensure_google_stub()
