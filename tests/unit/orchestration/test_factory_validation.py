import contextlib
import os
from types import SimpleNamespace

import pytest

from egregora.orchestration.factory import PipelineFactory


def make_config(pipeline_db: str, runs_db: str):
    return SimpleNamespace(database=SimpleNamespace(pipeline_db=pipeline_db, runs_db=runs_db))


def test_create_database_backends_requires_uri(tmp_path):
    config = make_config("", "duckdb:///:memory:")

    with pytest.raises(
        ValueError, match=r"Database setting 'database\.pipeline_db' must be a non-empty connection URI\."
    ):
        PipelineFactory.create_database_backends(tmp_path, config)


def test_create_database_backends_normalizes_duckdb_path(tmp_path):
    config = make_config("duckdb:///./data/pipeline.duckdb", "duckdb:///:memory:")

    runtime_uri, pipeline_backend, runs_backend = PipelineFactory.create_database_backends(tmp_path, config)

    expected_path = (tmp_path / "data" / "pipeline.duckdb").resolve()
    # On Windows, we use duckdb:C:/path to avoid double drive letter issues in Ibis
    if os.name == "nt":
        assert runtime_uri == f"duckdb:{expected_path.as_posix()}"
    else:
        assert runtime_uri == f"duckdb:///{expected_path}"
    assert expected_path.exists()

    with contextlib.suppress(Exception):
        # Ibis backends don't always have a close method, or it might fail on closed connections
        if hasattr(pipeline_backend, "close"):
            pipeline_backend.close()
    with contextlib.suppress(Exception):
        if hasattr(runs_backend, "close"):
            runs_backend.close()


def test_create_database_backends_validates_scheme(tmp_path):
    config = make_config("invalid-uri", "duckdb:///:memory:")

    with pytest.raises(
        ValueError,
        match=r"Database setting 'database\.pipeline_db' must be provided as an Ibis-compatible connection URI",
    ):
        PipelineFactory.create_database_backends(tmp_path, config)


def test_create_database_backends_rejects_filesystem_paths(tmp_path):
    # Windows path like C:/... is parsed as scheme='c'
    config = make_config("C:/path/to/db", "duckdb:///:memory:")

    with pytest.raises(
        ValueError, match=r"Database setting 'database\.pipeline_db' looks like a filesystem path"
    ):
        PipelineFactory.create_database_backends(tmp_path, config)

    # Unix paths have empty scheme
    config = make_config("/path/to/db", "duckdb:///:memory:")
    with pytest.raises(
        ValueError,
        match=r"Database setting 'database\.pipeline_db' must be provided as an Ibis-compatible connection URI",
    ):
        PipelineFactory.create_database_backends(tmp_path, config)


def test_create_database_backends_memory_normalization(tmp_path):
    config = make_config("duckdb:///:memory:", "duckdb:///:memory:")

    runtime_uri, _, _ = PipelineFactory.create_database_backends(tmp_path, config)
    assert runtime_uri == "duckdb://:memory:"
