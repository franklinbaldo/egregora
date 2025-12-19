import contextlib
from types import SimpleNamespace

import pytest

from egregora.orchestration.factory import PipelineFactory


def make_config(pipeline_db: str, runs_db: str):
    return SimpleNamespace(database=SimpleNamespace(pipeline_db=pipeline_db, runs_db=runs_db))


def test_create_database_backends_requires_uri(tmp_path):
    config = make_config("", "duckdb:///:memory:")

    with pytest.raises(ValueError):
        PipelineFactory.create_database_backends(tmp_path, config)


def test_create_database_backends_normalizes_duckdb_path(tmp_path):
    config = make_config("duckdb:///./data/pipeline.duckdb", "duckdb:///:memory:")

    runtime_uri, pipeline_backend, runs_backend = PipelineFactory.create_database_backends(tmp_path, config)

    expected_path = (tmp_path / "data" / "pipeline.duckdb").resolve()
    assert runtime_uri == f"duckdb:///{expected_path}"
    assert expected_path.exists()

    with contextlib.suppress(Exception):
        pipeline_backend.close()
    with contextlib.suppress(Exception):
        runs_backend.close()
