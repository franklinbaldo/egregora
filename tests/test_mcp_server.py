import asyncio


def test_mcp_server_main_runs(monkeypatch):
    from egregora.mcp_server import server

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
