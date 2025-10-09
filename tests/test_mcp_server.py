import asyncio
import shutil
import textwrap
from pathlib import Path
from uuid import uuid4

import pytest

from egregora.mcp_server import server


@pytest.fixture()
def prepared_rag_server(monkeypatch):
    base_tmp = Path("tests/_tmp")
    base_tmp.mkdir(parents=True, exist_ok=True)
    work_dir = base_tmp / f"mcp_{uuid4().hex}"
    posts_dir = work_dir / "posts"
    cache_dir = work_dir / "cache"
    posts_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    sample_posts = Path("tests/data/rag_posts/sample_group/daily")
    target_daily_dir = posts_dir / "sample_group" / "posts" / "daily"
    target_daily_dir.mkdir(parents=True, exist_ok=True)
    for source in sample_posts.glob("*.md"):
        shutil.copy(source, target_daily_dir / source.name)

    config_path = work_dir / "mcp.toml"
    config_path.write_text(
        textwrap.dedent(
            f"""
            [rag]
            posts_dir = "{posts_dir.as_posix()}"
            cache_dir = "{cache_dir.as_posix()}"
            vector_store_type = "simple"
            enable_cache = false
            top_k = 5
            min_similarity = 0.0
            exclude_recent_days = 0
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    rag_server = server.RAGServer(config_path=config_path)
    asyncio.run(rag_server.reindex(force=True))

    monkeypatch.setattr(server, "MCP_IMPORT_ERROR", None)
    monkeypatch.setattr(server, "rag_server", rag_server)

    try:
        yield rag_server
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        try:
            base_tmp.rmdir()
        except OSError:
            pass


def test_mcp_server_main_runs(monkeypatch):
    events: dict[str, bool] = {}

    class DummyApp:
        def run_stdio(self):
            class _Ctx:
                async def __aenter__(self_inner):
                    events["entered"] = True
                    return self_inner

                async def __aexit__(self_inner, exc_type, exc, tb):
                    events["exited"] = True

            return _Ctx()

    class DummyRAG:
        def __init__(self, config_path=None):
            self.config_path = config_path
            self.ensure_called = False

        async def ensure_indexed(self) -> None:
            self.ensure_called = True

    class DummyEvent:
        def __init__(self) -> None:
            self.called = False

        async def wait(self) -> None:
            self.called = True

    dummy_event = DummyEvent()
    dummy_rag = DummyRAG()

    monkeypatch.setattr(server, "MCP_IMPORT_ERROR", None)
    monkeypatch.setattr(server, "app", DummyApp())
    monkeypatch.setattr(server, "RAGServer", lambda config_path=None: dummy_rag)
    monkeypatch.setattr(server.asyncio, "Event", lambda: dummy_event)

    asyncio.run(server.main(config_path=None))

    assert dummy_rag.ensure_called
    assert dummy_event.called
    assert events.get("entered") and events.get("exited")


def test_rag_server_search_posts_integration(prepared_rag_server):
    hits = asyncio.run(
        prepared_rag_server.search_posts(
            query="governança de dados públicos",
            top_k=3,
            min_similarity=0.0,
            exclude_recent_days=0,
        )
    )

    assert hits, "esperava pelo menos um resultado relevante"
    assert any(
        "governança" in hit.node.get_content().lower()
        for hit in hits
    ), "conteúdo retornado não inclui o tema pesquisado"


def test_handle_call_tool_search_posts_formats_markdown(prepared_rag_server):
    responses = asyncio.run(
        server.handle_call_tool(
            "search_posts",
            {
                "query": "produtividade em equipes remotas",
                "top_k": 2,
                "min_similarity": 0.0,
                "exclude_recent_days": 0,
            },
        )
    )

    assert responses, "tool deve retornar ao menos um bloco TextContent"
    body = responses[0].text
    assert body.startswith("# Trechos Relevantes"), "markdown deveria ter cabeçalho padrão"
    assert "produtividade" in body.lower()


def test_handle_read_resource_returns_post_content(prepared_rag_server):
    content = asyncio.run(server.handle_read_resource("post://2024-04-18"))

    assert "# Diário 18/04/2024" in content
    assert "estratégia brasileira de inteligência artificial" in content
