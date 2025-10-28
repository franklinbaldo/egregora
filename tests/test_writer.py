import asyncio  # Needed for asyncio.run invoked in tests below.
import sys
from importlib import util
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any


def _install_ibis_stub() -> None:
    if "ibis" in sys.modules:
        return

    fake_ibis = ModuleType("ibis")
    fake_ibis._ = SimpleNamespace(count=lambda: None)
    fake_ibis.desc = lambda column: column
    sys.modules["ibis"] = fake_ibis

    fake_ibis_expr = ModuleType("ibis.expr")
    fake_ibis_expr_types = ModuleType("ibis.expr.types")
    fake_ibis_expr_types.Table = object
    sys.modules["ibis.expr"] = fake_ibis_expr
    sys.modules["ibis.expr.types"] = fake_ibis_expr_types


_install_ibis_stub()


def _install_rich_stub() -> None:
    if "rich" in sys.modules:
        return

    rich_module = ModuleType("rich")
    console_module = ModuleType("rich.console")
    progress_module = ModuleType("rich.progress")

    class DummyConsole:
        def __init__(self, *args, **kwargs):
            self.is_terminal = False

        def print(self, *args, **kwargs):  # noqa: D401 - mimic Console API
            """No-op print for tests."""

    class DummyProgress:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def add_task(self, *args, **kwargs):
            return 1

        def update(self, *args, **kwargs):
            pass

    class DummyColumn:
        def __init__(self, *args, **kwargs):
            pass

    console_module.Console = DummyConsole
    progress_module.Progress = DummyProgress
    progress_module.SpinnerColumn = DummyColumn
    progress_module.BarColumn = DummyColumn
    progress_module.TimeRemainingColumn = DummyColumn

    sys.modules["rich"] = rich_module
    sys.modules["rich.console"] = console_module
    sys.modules["rich.progress"] = progress_module


_install_rich_stub()


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

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _ensure_package_stub() -> None:
    package_name = "egregora"
    if package_name in sys.modules:
        return

    package = ModuleType(package_name)
    package.__path__ = [str(SRC_ROOT / package_name)]
    package.__spec__ = ModuleSpec(name=package_name, loader=None, is_package=True)
    package.__spec__.submodule_search_locations = package.__path__
    sys.modules[package_name] = package


_ensure_package_stub()

annotations_spec = util.spec_from_file_location(
    "egregora.annotations",
    SRC_ROOT / "egregora" / "annotations.py",
)
assert annotations_spec and annotations_spec.loader  # noqa: S101
annotations_module = util.module_from_spec(annotations_spec)
sys.modules["egregora.annotations"] = annotations_module
annotations_spec.loader.exec_module(annotations_module)


def _call_with_retries_sync(sync_fn, *args, **kwargs):
    return sync_fn(*args, **kwargs)


genai_utils_stub = ModuleType("egregora.genai_utils")
genai_utils_stub.call_with_retries = _call_with_retries_sync
genai_utils_stub.call_with_retries_sync = _call_with_retries_sync
sys.modules["egregora.genai_utils"] = genai_utils_stub


model_config_stub = ModuleType("egregora.model_config")


class _StubModelConfig:
    def get_model(self, name: str) -> str:
        return name


model_config_stub.ModelConfig = _StubModelConfig
sys.modules["egregora.model_config"] = model_config_stub


profiler_stub = ModuleType("egregora.profiler")


def _stub_get_active_authors(df):
    return []


def _stub_read_profile(author_uuid, profiles_dir=None):
    return ""


def _stub_write_profile(author_uuid, content, profiles_dir=None):
    return ""


profiler_stub.get_active_authors = _stub_get_active_authors
profiler_stub.read_profile = _stub_read_profile
profiler_stub.write_profile = _stub_write_profile
sys.modules["egregora.profiler"] = profiler_stub


prompt_templates_spec = util.spec_from_file_location(
    "egregora.prompt_templates",
    SRC_ROOT / "egregora" / "prompt_templates.py",
)
assert prompt_templates_spec and prompt_templates_spec.loader  # noqa: S101
prompt_templates_module = util.module_from_spec(prompt_templates_spec)
sys.modules["egregora.prompt_templates"] = prompt_templates_module
prompt_templates_spec.loader.exec_module(prompt_templates_module)


rag_stub = ModuleType("egregora.rag")


class _StubVectorStore:
    def __init__(self, *args, **kwargs):
        pass


async def _stub_index_post(*args, **kwargs):
    return None


async def _stub_query_media(*args, **kwargs):
    raise RuntimeError("media search not available in tests")


async def _stub_query_similar_posts(*args, **kwargs):
    class _Empty:
        def count(self):
            return SimpleNamespace(execute=lambda: 0)

    return _Empty()


rag_stub.VectorStore = _StubVectorStore
rag_stub.index_post = _stub_index_post
rag_stub.query_media = _stub_query_media
rag_stub.query_similar_posts = _stub_query_similar_posts
sys.modules["egregora.rag"] = rag_stub


site_config_stub = ModuleType("egregora.site_config")


def _stub_load_site_config(output_dir):
    return {}


def _stub_load_mkdocs_config(output_dir):
    return {}, None


site_config_stub.load_site_config = _stub_load_site_config
site_config_stub.load_mkdocs_config = _stub_load_mkdocs_config
sys.modules["egregora.site_config"] = site_config_stub


write_post_stub = ModuleType("egregora.write_post")


def _stub_write_post(*args, **kwargs):
    return ""


write_post_stub.write_post = _stub_write_post
sys.modules["egregora.write_post"] = write_post_stub

SPEC = util.spec_from_file_location(
    "egregora.writer",
    SRC_ROOT / "egregora" / "writer.py",
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

        def generate_content(self, *args, **kwargs):  # noqa: D401
            """Return a canned response for tests."""

            return self._response

    class DummyAio:
        def __init__(self, response_obj):
            self.models = DummyModels(response_obj)

    class DummyClient:
        def __init__(self, response_obj):
            self.aio = DummyAio(response_obj)
            # Ensure synchronous code paths can access the same models stub.
            self.models = self.aio.models

    captured_request: dict[str, Any] = {}

    def immediate_call(sync_fn, *args, **kwargs):
        if "contents" in kwargs:
            captured_request["contents"] = kwargs["contents"]
        elif args:
            captured_request["contents"] = args[0]
        return sync_fn(*args, **kwargs)

    monkeypatch.setattr(writer, "call_with_retries_sync", immediate_call)
    monkeypatch.setattr(writer, "get_active_authors", lambda df: ["user-1"])
    monkeypatch.setattr(writer, "_load_profiles_context", lambda df, profiles_dir: "")

    client = DummyClient(response)
    output_dir = tmp_path / "posts"
    profiles_dir = tmp_path / "profiles"
    rag_dir = tmp_path / "rag"

    batch_client = SimpleNamespace()

    result = writer.write_posts_for_period(
        df,
        date="2024-05-01",
        client=client,
        batch_client=batch_client,
        output_dir=output_dir,
        profiles_dir=profiles_dir,
        rag_dir=rag_dir,
        enable_rag=False,
    )

    assert len(result["posts"]) == 1

    saved_path = output_dir / "freeform" / "2024-05-01-freeform.md"
    assert saved_path.exists()
    saved_content = saved_path.read_text(encoding="utf-8")

    assert freeform_text in saved_content
    assert "title: Freeform Response (2024-05-01)" in saved_content
    assert "date: 2024-05-01" in saved_content

    annotation_db = (output_dir.parent / "annotations.duckdb").resolve()
    assert annotation_db.exists()

    assert "contents" in captured_request
    initial_message = captured_request["contents"][0].parts[0].text
    assert "| msg_id |" in initial_message
    assert "Annotation Memory Tool" in initial_message

    records = df.execute().to_dict("records")
    expected_msg_id = writer._compute_message_id(records[0])
    assert expected_msg_id in initial_message
