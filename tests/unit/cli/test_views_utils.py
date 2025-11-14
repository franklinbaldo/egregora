"""Tests for CLI view utility helpers."""
from __future__ import annotations

from pathlib import Path

import pytest
import typer
from rich.console import Console

from egregora.cli.commands import views_utils


class DummyConnection:
    """Simple stand-in for a DuckDB connection used in tests."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_view_registry_requires_existing_db(tmp_path: Path) -> None:
    console = Console(record=True)
    missing_db = tmp_path / "missing.duckdb"

    with pytest.raises(typer.Exit):
        with views_utils.view_registry_context(console, missing_db, require_db=True):
            pass


def test_view_registry_closes_on_registry_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    console = Console(record=True)
    db_path = tmp_path / "registry.duckdb"
    db_path.write_text("")

    connection = DummyConnection()

    monkeypatch.setattr(views_utils, "_connect_duckdb", lambda path, read_only=False: connection)

    def failing_registry(_conn: DummyConnection, _table: str) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(views_utils, "_create_registry", failing_registry)

    with pytest.raises(typer.Exit):
        with views_utils.view_registry_context(console, db_path, require_db=True):
            pass

    assert connection.closed is True


def test_view_registry_context_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    console = Console(record=True)
    db_path = tmp_path / "success.duckdb"
    db_path.write_text("")

    connection = DummyConnection()
    registry = object()

    def fake_connect(path: Path, read_only: bool = False) -> DummyConnection:
        assert path == db_path
        assert read_only is False
        return connection

    def fake_registry(conn: DummyConnection, table_name: str) -> object:
        assert conn is connection
        assert table_name == "messages"
        return registry

    monkeypatch.setattr(views_utils, "_connect_duckdb", fake_connect)
    monkeypatch.setattr(views_utils, "_create_registry", fake_registry)

    with views_utils.view_registry_context(console, db_path, require_db=True) as (conn, reg):
        assert conn is connection
        assert reg is registry

    assert connection.closed is True


def test_ensure_view_registered_errors() -> None:
    console = Console(record=True)

    class DummyRegistry:
        def list_views(self) -> list[str]:
            return ["foo", "bar"]

    registry = DummyRegistry()

    with pytest.raises(typer.Exit):
        views_utils.ensure_view_registered(console, registry, "baz")
