"""Unit tests for CLI view helper utilities."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import typer

from egregora.cli.commands import views_utils


class DummyConnection:
    """Test double for DuckDB connection."""

    def __init__(self, tables: list[str] | None = None) -> None:
        self._tables = tables or []
        self.closed = False
        self.execute = MagicMock(side_effect=self._execute)

    def _execute(self, _query: str) -> SimpleNamespace:
        return SimpleNamespace(fetchall=lambda: [(name,) for name in self._tables])

    def close(self) -> None:
        self.closed = True


def test_view_registry_context_requires_existing_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing database path should trigger a typer.Exit before connecting."""
    connect_mock = MagicMock()
    monkeypatch.setattr(views_utils.duckdb, "connect", connect_mock)

    missing_db = tmp_path / "missing.duckdb"
    with pytest.raises(typer.Exit):
        with views_utils.view_registry_context(missing_db, require_db=True):
            pass

    connect_mock.assert_not_called()
    captured = capsys.readouterr()
    assert "Database file not found" in captured.out


def test_view_registry_context_registers_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The helper should register common views and close the connection."""
    dummy_conn = DummyConnection()
    monkeypatch.setattr(views_utils.duckdb, "connect", MagicMock(return_value=dummy_conn))

    created_registry: list[object] = []

    class DummyRegistry:
        def __init__(self, conn: DummyConnection) -> None:
            created_registry.append(conn)

    monkeypatch.setattr(views_utils, "ViewRegistry", DummyRegistry)

    register_called: list[tuple[object, str]] = []

    def fake_register(registry: object, *, table_name: str = "messages") -> None:
        register_called.append((registry, table_name))

    monkeypatch.setattr(views_utils, "register_common_views", fake_register)

    with views_utils.view_registry_context(Path("db.duckdb")) as (conn, registry):
        assert conn is dummy_conn
        assert isinstance(registry, DummyRegistry)

    assert dummy_conn.closed
    assert created_registry == [dummy_conn]
    assert register_called == [(registry, "messages")]


def test_view_registry_context_missing_table(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Requiring a table should fail when the table is absent and avoid registration."""
    dummy_conn = DummyConnection(tables=["other_table"])
    monkeypatch.setattr(views_utils.duckdb, "connect", MagicMock(return_value=dummy_conn))
    register_mock = MagicMock()
    monkeypatch.setattr(views_utils, "register_common_views", register_mock)

    with pytest.raises(typer.Exit):
        with views_utils.view_registry_context(
            Path("db.duckdb"),
            table_name="messages",
            require_table=True,
        ):
            pass

    captured = capsys.readouterr()
    assert "Table 'messages' not found" in captured.out
    register_mock.assert_not_called()
    assert dummy_conn.closed


def test_ensure_view_registered_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Missing views should surface a helpful error before exiting."""
    registry = MagicMock()
    registry.get_view.side_effect = KeyError("boom")
    registry.list_views.return_value = ["alpha", "beta"]

    with pytest.raises(typer.Exit):
        views_utils.ensure_view_registered(registry, "gamma")

    captured = capsys.readouterr()
    assert "View 'gamma' not registered" in captured.out
    assert "alpha" in captured.out


def test_ensure_view_registered_materialized_requirement(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The helper should guard against refreshing non-materialized views."""
    view = SimpleNamespace(materialized=False)
    registry = MagicMock()
    registry.get_view.return_value = view

    with pytest.raises(typer.Exit):
        views_utils.ensure_view_registered(registry, "alpha", require_materialized=True)

    captured = capsys.readouterr()
    assert "is not materialized" in captured.out
