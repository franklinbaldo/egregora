"""Tests for the TJRO IPERON adapter."""

from __future__ import annotations

from pathlib import Path

from egregora.input_adapters.iperon_tjro import IperonTJROAdapter


import ibis


def test_adapter_parses_mock_payload(tmp_path: Path):
    adapter = IperonTJROAdapter()
    config_path = tmp_path / "sample.json"
    fixture = Path("tests/fixtures/input/iperon_tjro/sample.json")
    config_path.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    table = adapter.parse(config_path)

    assert isinstance(table, ibis.expr.types.Table)
    assert table.count().execute() == 2

    df = table.execute()
    first = df.iloc[0]
    second = df.iloc[1]

    assert first["doc_type"] == "post"
    assert first["status"] == "published"
    assert first["title"].startswith("Communication from TJRO")
    assert first["content"]

    assert isinstance(second["authors"], list)
    assert second["created_at"] is not None

    assert "TJRO" in adapter.content_summary
