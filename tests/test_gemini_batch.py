import sys
import types
from types import SimpleNamespace

# Provide minimal google genai stubs when optional dependency is absent.
if "google" not in sys.modules:
    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.genai")
    genai_types_module = types.ModuleType("google.genai.types")

    class _Stub:  # pragma: no cover - simple struct placeholder
        def __init__(self, *_, **__):
            pass

    genai_types_module.Part = _Stub
    genai_types_module.Content = _Stub
    genai_types_module.InlinedRequest = _Stub
    genai_types_module.BatchJobSource = _Stub
    genai_types_module.CreateBatchJobConfig = _Stub
    genai_types_module.GenerateContentConfig = _Stub

    google_module.genai = genai_module
    genai_module.types = genai_types_module

    sys.modules["google"] = google_module
    sys.modules["google.genai"] = genai_module
    sys.modules["google.genai.types"] = genai_types_module

from egregora import genai_utils
from egregora.gemini_batch import BatchPromptRequest, GeminiBatchClient


class FlakyBatches:
    """Stub Gemini batches API that fails once with a rate limit error."""

    def __init__(self) -> None:
        self.create_attempts = 0
        self.get_calls = 0

    def create(self, *_, **__):  # pragma: no cover - simple stub
        self.create_attempts += 1
        if self.create_attempts == 1:
            raise RuntimeError("429 Too Many Requests: slow down")
        return SimpleNamespace(name="jobs/123", done=False, state=None, dest=None, error=None)

    def get(self, name: str):  # pragma: no cover - simple stub
        self.get_calls += 1
        if self.get_calls == 1:
            return SimpleNamespace(
                name=name,
                done=False,
                state=SimpleNamespace(name="JOB_STATE_PROCESSING"),
                dest=None,
                error=None,
            )

        response_obj = SimpleNamespace(response=SimpleNamespace(text="ok"), error=None)
        dest = SimpleNamespace(inlined_responses=[response_obj])
        return SimpleNamespace(
            name=name,
            done=True,
            state=SimpleNamespace(name="JOB_STATE_SUCCEEDED"),
            dest=dest,
            error=None,
        )


def test_batch_client_retries_rate_limited_create(monkeypatch):
    """The batch client should retry when job creation hits a rate limit."""

    monkeypatch.setattr(genai_utils, "_respect_min_interval_sync", lambda: None)
    monkeypatch.setattr(genai_utils, "_sleep_with_progress_sync", lambda delay, description: None)
    monkeypatch.setattr(genai_utils, "_MIN_INTERVAL_SECONDS", 0.0, raising=False)

    client = SimpleNamespace(batches=FlakyBatches())
    batch_client = GeminiBatchClient(client=client, default_model="models/test", poll_interval=0.0, timeout=5.0)

    requests = [BatchPromptRequest(contents=[object()], tag="tag-1")]

    results = batch_client.generate_content(requests)

    assert client.batches.create_attempts == 2, "should retry the initial create call"
    assert len(results) == 1
    assert results[0].response.text == "ok"
