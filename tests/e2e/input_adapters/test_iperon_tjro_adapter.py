"""Tests for the TJRO IPERON adapter."""

from __future__ import annotations

from pathlib import Path

from egregora.input_adapters.iperon_tjro import IperonTJROAdapter


class _FakeTable:
    def __init__(self, data, schema):
        self.data = data
        self._schema = schema

    def schema(self):
        return self._schema


def test_adapter_parses_mock_payload(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}

    def fake_memtable(data, schema=None, columns=None):
        captured["rows"] = data
        captured["schema"] = schema
        return _FakeTable(data, schema)

    monkeypatch.setattr(
        "egregora.input_adapters.iperon_tjro.ibis.memtable",
        fake_memtable,
    )

    adapter = IperonTJROAdapter()
    config_path = tmp_path / "sample.json"
    fixture = Path("tests/fixtures/input/iperon_tjro/sample.json")
    config_path.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    table = adapter.parse(config_path)

    assert isinstance(table, _FakeTable)
    assert table.schema() == captured["schema"]

    rows = captured["rows"]
    assert len(rows) == 2
    first, second = rows

    assert first["tenant_id"] == "TJRO"
    assert first["source"] == adapter.source_identifier
    assert first["thread_id"].startswith("7000000")
    assert first["text"]
    assert first["media_type"] == "url"

    assert second["author_raw"] == "Secretaria"
    assert second["thread_id"] == str(second["event_id"])
    assert second["ts"] is not None

    assert "TJRO" in adapter.content_summary
