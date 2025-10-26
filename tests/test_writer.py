import asyncio  # Needed for asyncio.run invoked in tests below.
import sys
from importlib import util
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _install_google_stubs() -> None:
    if "google" in sys.modules:
        return

    fake_google = ModuleType("google")
    fake_genai = ModuleType("google.genai")

    class DummyType:
        OBJECT = "object"
        STRING = "string"
        ARRAY = "array"
        INTEGER = "integer"

    class DummySchema:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class DummyFunctionDeclaration:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class DummyTool:
        def __init__(self, function_declarations):
            self.function_declarations = function_declarations

    class DummyFunctionResponse:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class DummyPart:
        def __init__(self, text=None, function_call=None, function_response=None):
            self.text = text
            self.function_call = function_call
            self.function_response = function_response

    class DummyContent:
        def __init__(self, role: str, parts: list[DummyPart]):
            self.role = role
            self.parts = parts

    class DummyGenerateContentConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class DummyEmbedContentConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_types = ModuleType("google.genai.types")
    fake_types.Type = DummyType
    fake_types.Schema = DummySchema
    fake_types.FunctionDeclaration = DummyFunctionDeclaration
    fake_types.Tool = DummyTool
    fake_types.FunctionResponse = DummyFunctionResponse
    fake_types.Part = DummyPart
    fake_types.Content = DummyContent
    fake_types.GenerateContentConfig = DummyGenerateContentConfig
    fake_types.EmbedContentConfig = DummyEmbedContentConfig

    fake_google.genai = fake_genai
    fake_genai.types = fake_types
    fake_genai.Client = SimpleNamespace

    sys.modules["google"] = fake_google
    sys.modules["google.genai"] = fake_genai
    sys.modules["google.genai.types"] = fake_types


_install_google_stubs()


def _ensure_package_stub() -> None:
    package_name = "egregora"
    if package_name in sys.modules:
        return

    package = ModuleType(package_name)
    package.__path__ = [
        str(Path(__file__).resolve().parents[1] / "src" / package_name)
    ]
    sys.modules[package_name] = package


_ensure_package_stub()

SPEC = util.spec_from_file_location(
    "egregora.writer",
    Path(__file__).resolve().parents[1] / "src" / "egregora" / "writer.py",
)
writer = util.module_from_spec(SPEC)
assert SPEC and SPEC.loader  # noqa: S101 - ensure spec is valid for mypy
sys.modules["egregora.writer"] = writer
SPEC.loader.exec_module(writer)


class DummyQueryResult:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class DummyTable:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def count(self) -> DummyQueryResult:
        return DummyQueryResult(len(self._rows))

    def execute(self):
        import pandas as pd

        return pd.DataFrame(self._rows)


def test_write_freeform_markdown_creates_file(tmp_path):
    output_dir = tmp_path / "posts"
    content = "This is a freeform response."
    date = "2024-05-01"

    path = writer._write_freeform_markdown(content, date, output_dir)

    assert path.exists()
    assert path.read_text(encoding="utf-8") == (
        "---\n"
        "title: Freeform Response (2024-05-01)\n"
        "date: 2024-05-01\n"
        "---\n\n"
        "This is a freeform response.\n"
    )


def test_write_posts_for_period_saves_freeform_response(tmp_path, monkeypatch):
    df = DummyTable(
        [
            {
                "author": "user-1",
                "message": "Hello world",
                "timestamp": "2024-05-01T10:00:00",
            }
        ]
    )

    freeform_text = "Here is a summary without tool calls."

    text_part = SimpleNamespace(text=freeform_text, function_call=None)
    content = SimpleNamespace(parts=[text_part])
    candidate = SimpleNamespace(content=content)
    response = SimpleNamespace(candidates=[candidate])

    class DummyModels:
        def __init__(self, response_obj):
            self._response = response_obj

        async def generate_content(self, *args, **kwargs):  # noqa: D401
            """Return a canned response for tests."""

            return self._response

    class DummyAio:
        def __init__(self, response_obj):
            self.models = DummyModels(response_obj)

    class DummyClient:
        def __init__(self, response_obj):
            self.aio = DummyAio(response_obj)

    async def immediate_call(async_fn, *args, **kwargs):
        return await async_fn(*args, **kwargs)

    monkeypatch.setattr(writer, "call_with_retries", immediate_call)
    monkeypatch.setattr(writer, "get_active_authors", lambda df: ["user-1"])
    monkeypatch.setattr(writer, "_load_profiles_context", lambda df, profiles_dir: "")

    client = DummyClient(response)
    output_dir = tmp_path / "posts"
    profiles_dir = tmp_path / "profiles"
    rag_dir = tmp_path / "rag"

    result = asyncio.run(
        writer.write_posts_for_period(
            df,
            date="2024-05-01",
            client=client,
            output_dir=output_dir,
            profiles_dir=profiles_dir,
            rag_dir=rag_dir,
            enable_rag=False,
        )
    )

    assert len(result["posts"]) == 1

    saved_path = output_dir / "freeform" / "2024-05-01-freeform.md"
    assert saved_path.exists()
    saved_content = saved_path.read_text(encoding="utf-8")

    assert freeform_text in saved_content
    assert "title: Freeform Response (2024-05-01)" in saved_content
    assert "date: 2024-05-01" in saved_content
