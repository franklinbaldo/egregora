"""Tests for the RAG module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest
from typer.testing import CliRunner
import polars as pl

from egregora.rag_context.main import app

runner = CliRunner()


@pytest.fixture
def mock_run_server():
    """Mocks the run_server function."""
    with patch("egregora.rag_context.main.run_server") as mock:
        yield mock


def test_rag_serve_command(mock_run_server):
    """Tests that the `rag serve` command starts the FastMCP server."""
    result = runner.invoke(app, ["dummy.parquet"])
    assert result.exit_code == 0
    mock_run_server.assert_called_once_with(Path("dummy.parquet"))
