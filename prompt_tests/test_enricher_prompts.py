import asyncio
import sys
import types
from dataclasses import dataclass
from pathlib import Path

sys.modules.pop("ibis", None)
sys.modules.pop("ibis.expr", None)
sys.modules.pop("ibis.expr.types", None)
sys.modules.pop("ibis.expr.datatypes", None)
sys.modules.pop("ibis.common", None)
sys.modules.pop("ibis.common.exceptions", None)
sys.modules.pop("ibis.common.datatypes", None)
# Stub pydantic_ai and dependencies before importing project code.
pydantic_ai = types.ModuleType("pydantic_ai")
messages_mod = types.ModuleType("pydantic_ai.messages")


@dataclass
class _StubBinaryContent:
    data: bytes
    media_type: str


class _StubModelRequest:  # pragma: no cover - placeholder
    pass


messages_mod.BinaryContent = _StubBinaryContent
messages_mod.ModelRequest = _StubModelRequest
messages_mod.ModelResponse = type("ModelResponse", (), {})
messages_mod.__getattr__ = lambda name: type(name, (), {})

exceptions_mod = types.ModuleType("pydantic_ai.exceptions")
exceptions_mod.UnexpectedModelBehavior = Exception

agent_mod = types.ModuleType("pydantic_ai.agent")
agent_mod.Agent = object
agent_mod.AgentRunResult = object
agent_mod.RunContext = object

models_mod = types.ModuleType("pydantic_ai.models")
google_models_mod = types.ModuleType("pydantic_ai.models.google")
google_models_mod.GoogleModelSettings = object
models_mod.google = google_models_mod
usage_mod = types.ModuleType("pydantic_ai.usage")
usage_mod.Usage = object
usage_mod.RunUsage = object

pydantic_ai.Agent = agent_mod.Agent
pydantic_ai.AgentRunResult = agent_mod.AgentRunResult
pydantic_ai.RunContext = agent_mod.RunContext
pydantic_ai.messages = messages_mod
pydantic_ai.exceptions = exceptions_mod
pydantic_ai.models = models_mod
pydantic_ai.usage = usage_mod

sys.modules.setdefault("pydantic_ai", pydantic_ai)
sys.modules.setdefault("pydantic_ai.messages", messages_mod)
sys.modules.setdefault("pydantic_ai.exceptions", exceptions_mod)
sys.modules.setdefault("pydantic_ai.agent", agent_mod)
sys.modules.setdefault("pydantic_ai.models", models_mod)
sys.modules.setdefault("pydantic_ai.models.google", google_models_mod)
sys.modules.setdefault("pydantic_ai.usage", usage_mod)

# Stub ibis to avoid heavy imports and runtime decorators during test collection.
ibis_mod = types.ModuleType("ibis")
expr_mod = types.ModuleType("ibis.expr")
expr_types_mod = types.ModuleType("ibis.expr.types")
expr_types_mod.Table = object
expr_mod.types = expr_types_mod
expr_mod.datatypes = None  # set after dt_mod defined
ibis_mod.expr = expr_mod
ibis_mod.options = types.SimpleNamespace(default_backend=None)
ibis_mod.duckdb = types.SimpleNamespace(from_connection=lambda conn=None: None)
ibis_mod.schema = lambda mapping: mapping
ibis_common_mod = types.ModuleType("ibis.common")
ibis_common_mod.exceptions = types.SimpleNamespace(IbisError=Exception)
dt_mod = types.ModuleType("ibis.expr.datatypes")


class _StubDataType:
    def __init__(self, name: str | None = None, *args, **kwargs) -> None:
        self.name = name
        self.args = args
        self.kwargs = kwargs


class _StubTimestamp(_StubDataType):
    def __init__(self, timezone=None, scale=None, nullable=False) -> None:
        super().__init__(timezone=timezone, scale=scale, nullable=nullable)
        self.timezone = timezone
        self.scale = scale
        self.nullable = nullable


class _StubString(_StubDataType):
    def __init__(self, nullable=False) -> None:
        super().__init__(nullable=nullable)
        self.nullable = nullable


class _StubJSON(_StubDataType):
    def __init__(self, nullable=False) -> None:
        super().__init__(nullable=nullable)
        self.nullable = nullable


class _StubUUID(_StubDataType):
    def __init__(self, nullable=False) -> None:
        super().__init__(nullable=nullable)
        self.nullable = nullable


dt_mod.DataType = _StubDataType
dt_mod.Timestamp = _StubTimestamp
dt_mod.String = _StubString
dt_mod.JSON = _StubJSON
dt_mod.UUID = _StubUUID
dt_mod.string = lambda *args, **kwargs: "string"
dt_mod.date = lambda *args, **kwargs: "date"
dt_mod.__getattr__ = lambda name: (lambda *args, **kwargs: _StubDataType(name, *args, **kwargs))
expr_mod.datatypes = dt_mod

ibis_mod.Table = object
ibis_mod.udf = types.SimpleNamespace(
    scalar=lambda *args, **kwargs: (lambda func: func),
    aggregate=lambda *args, **kwargs: (lambda func: func),
    python=lambda *args, **kwargs: (lambda func: func),
)
ibis_mod.genus = None
ibis_mod.Client = object
sys.modules["ibis"] = ibis_mod
sys.modules["ibis.expr"] = expr_mod
sys.modules["ibis.expr.types"] = expr_types_mod
sys.modules["ibis.expr.datatypes"] = dt_mod
sys.modules["ibis.common"] = ibis_common_mod
sys.modules["ibis.common.exceptions"] = ibis_common_mod.exceptions

# Stub google modules
_google_module = types.ModuleType("google")
_google_genai = types.ModuleType("google.genai")
_google_genai.Client = object
_google_genai.types = types.SimpleNamespace()
_google_genai.errors = types.SimpleNamespace(GoogleAPICallError=Exception, ServerError=Exception)

_google_api_core = types.ModuleType("google.api_core")
_google_api_core.exceptions = types.SimpleNamespace(
    GoogleAPIError=Exception,
    ResourceExhausted=Exception,
    ServiceUnavailable=Exception,
    InternalServerError=Exception,
    GatewayTimeout=Exception,
)

_google_module.genai = _google_genai
_google_module.api_core = _google_api_core
sys.modules.setdefault("google", _google_module)
sys.modules.setdefault("google.genai", _google_genai)
sys.modules.setdefault("google.api_core", _google_api_core)


# Stub whatsapp adapter to avoid heavy dependencies during tests.
whatsapp_adapter_mod = types.ModuleType("egregora.input_adapters.whatsapp.adapter")


class _StubWhatsAppAdapter:
    pass


whatsapp_adapter_mod.WhatsAppAdapter = _StubWhatsAppAdapter
whatsapp_pkg_mod = types.ModuleType("egregora.input_adapters.whatsapp")
whatsapp_pkg_mod.adapter = whatsapp_adapter_mod
whatsapp_pkg_mod.commands = types.ModuleType("egregora.input_adapters.whatsapp.commands")
sys.modules["egregora.input_adapters.whatsapp"] = whatsapp_pkg_mod
sys.modules["egregora.input_adapters.whatsapp.adapter"] = whatsapp_adapter_mod
sys.modules["egregora.input_adapters.whatsapp.commands"] = whatsapp_pkg_mod.commands

# Stub _griffe extension expected by pydantic-ai
_griffe_module = types.ModuleType("_griffe")
_griffe_enums = types.ModuleType("_griffe.enumerations")
_griffe_models = types.ModuleType("_griffe.models")


class _DocstringSectionKind:  # minimal placeholder
    pass


class _DummyDocstring:  # pragma: no cover - placeholder
    pass


class _DummyObject:  # pragma: no cover - placeholder
    pass


_griffe_enums.DocstringSectionKind = _DocstringSectionKind
_griffe_models.Docstring = _DummyDocstring
_griffe_models.Object = _DummyObject

sys.modules.setdefault("_griffe", _griffe_module)
sys.modules.setdefault("_griffe.enumerations", _griffe_enums)
sys.modules.setdefault("_griffe.models", _griffe_models)

_griffe_module.enumerations = _griffe_enums
_griffe_module.models = _griffe_models

from egregora.agents.enricher import (
    EnrichmentOutput,
    MediaEnrichmentDeps,
    UrlEnrichmentDeps,
    _run_media_enrichment_async,
    _run_url_enrichment_async,
)


@dataclass
class _FakeBinaryContent:
    data: bytes
    media_type: str


class _FakeResult:
    def __init__(self, markdown: str, slug: str = "sluggy") -> None:
        self.data = EnrichmentOutput(markdown=markdown, slug=slug)

    def usage(self) -> dict[str, int]:
        return {"input_tokens": 1}


class _FakeAgent:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object]] = []

    async def run(self, prompt, deps):  # noqa: ANN001
        self.calls.append((prompt, deps))
        return _FakeResult(" some content \n")


def test_run_url_enrichment_builds_prompt_with_sanitized_context(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "enrichment_url.jinja").write_text("URL: {{ sanitized_url }}", encoding="utf-8")

    raw_url = "https://example.com\n\n  space"
    agent = _FakeAgent()

    output, usage = asyncio.run(_run_url_enrichment_async(agent, raw_url, prompts_dir))

    assert agent.calls, "Agent run was not invoked"
    prompt_arg, deps = agent.calls[0]
    assert prompt_arg == "URL: https://example.com\nspace"
    assert isinstance(deps, UrlEnrichmentDeps)
    assert deps.url == "https://example.com\nspace"
    assert deps.prompts_dir == prompts_dir
    assert output.markdown == "some content"
    assert usage == {"input_tokens": 1}


def test_run_media_enrichment_passes_sanitized_metadata(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "enrichment_media.jinja").write_text(
        "FILE: {{ sanitized_filename }}{% if sanitized_mime %} ({{ sanitized_mime }}){% endif %}",
        encoding="utf-8",
    )

    agent = _FakeAgent()
    payload = _FakeBinaryContent(data=b"123", media_type="image/png")

    output, usage = asyncio.run(
        _run_media_enrichment_async(
            agent,
            filename="file\\name\n",
            mime_hint="image/png\n",
            prompts_dir=prompts_dir,
            binary_content=payload,
        )
    )

    assert agent.calls, "Agent run was not invoked"
    prompt_arg, deps = agent.calls[0]
    assert prompt_arg[0] == "FILE: filename (image/png)"
    assert isinstance(deps, MediaEnrichmentDeps)
    assert deps.media_filename == "filename"
    assert deps.media_type == "image/png"
    assert deps.prompts_dir == prompts_dir
    assert output.markdown == "some content"
    assert usage == {"input_tokens": 1}
