"""Tests for the TJRO IPERON adapter."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from egregora.input_adapters.iperon_tjro import IperonTJROAdapter


def test_adapter_parses_mock_payload(tmp_path: Path):
    adapter = IperonTJROAdapter()
    config_path = tmp_path / "sample.json"
    fixture = Path("tests/fixtures/input/iperon_tjro/sample.json")
    config_path.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    table = adapter.parse(config_path)
    df = table.execute()

    assert isinstance(df, pd.DataFrame)
    assert df.shape[0] == 2
    assert set(df.columns) == set(table.schema().names)

    first = df.iloc[0]
    assert first["tenant_id"] == "TJRO"
    assert first["source"] == adapter.source_identifier
    assert first["thread_id"].startswith("7000000")
    assert first["text"]
    assert first["media_type"] == "url"

    second = df.iloc[1]
    assert second["author_raw"] == "Secretaria"
    assert second["thread_id"] == str(second["event_id"])
    assert pd.notna(second["ts"]) and second["ts"].tzinfo is not None

    assert "TJRO" in adapter.content_summary
