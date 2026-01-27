import contextlib
from types import SimpleNamespace

import pytest

<<<<<<< HEAD
from egregora.config.exceptions import InvalidDatabaseUriError, SiteStructureError
from egregora.orchestration.pipelines.etl.setup import _create_database_backend, _resolve_site_paths_or_raise
=======
from egregora.orchestration.factory import PipelineFactory
from egregora.config.exceptions import InvalidDatabaseUriError, SiteStructureError
from egregora.config.settings import EgregoraConfig
>>>>>>> origin/pr/2747


def make_config(pipeline_db: str):
    return SimpleNamespace(database=SimpleNamespace(pipeline_db=pipeline_db))


def test_create_database_backends_requires_uri(tmp_path):
    config = make_config("")

    with pytest.raises(
<<<<<<< HEAD
        ValueError, match=r"Database setting 'database\.pipeline_db' must be a non-empty"
=======
        InvalidDatabaseUriError, match=r"Database setting 'database\.pipeline_db' must be non-empty\."
>>>>>>> origin/pr/2747
    ):
        _create_database_backend(tmp_path, config)


def test_create_database_backends_normalizes_duckdb_path(tmp_path):
    config = make_config("duckdb:///./data/pipeline.duckdb")

    runtime_uri, pipeline_backend = _create_database_backend(tmp_path, config)

    expected_path = (tmp_path / "data" / "pipeline.duckdb").resolve()
    # On Windows, we use duckdb:C:/path to avoid double drive letter issues in Ibis
    import os

    if os.name == "nt":
        assert runtime_uri == f"duckdb:{expected_path.as_posix()}"
    else:
        assert runtime_uri == f"duckdb://{expected_path}"
    assert expected_path.exists()

    with contextlib.suppress(Exception):
        pipeline_backend.close()


<<<<<<< HEAD
def test_resolve_site_paths_missing_mkdocs(tmp_path, minimal_config):
    """Test that resolve_site_paths_or_raise raises ValueError if mkdocs.yml is missing."""
    config = minimal_config

    with pytest.raises(ValueError, match=r"No mkdocs\.yml found"):
        _resolve_site_paths_or_raise(tmp_path, config)


def test_resolve_site_paths_missing_docs_dir(tmp_path, minimal_config):
    """Test that resolve_site_paths_or_raise raises ValueError if docs/ is missing."""
    config = minimal_config
=======
def test_resolve_site_paths_missing_mkdocs(tmp_path):
    """Test that resolve_site_paths_or_raise raises SiteStructureError if mkdocs.yml is missing."""
    config = EgregoraConfig()

    with pytest.raises(SiteStructureError, match="No mkdocs.yml found"):
        PipelineFactory.resolve_site_paths_or_raise(tmp_path, config)


def test_resolve_site_paths_missing_docs_dir(tmp_path):
    """Test that resolve_site_paths_or_raise raises SiteStructureError if docs/ is missing."""
    config = EgregoraConfig()
>>>>>>> origin/pr/2747

    # Create .egregora/mkdocs.yml so first check passes
    (tmp_path / ".egregora").mkdir()
    (tmp_path / ".egregora" / "mkdocs.yml").touch()

<<<<<<< HEAD
    with pytest.raises(ValueError, match="Docs directory not found"):
        _resolve_site_paths_or_raise(tmp_path, config)
=======
    with pytest.raises(SiteStructureError, match="Docs directory not found"):
        PipelineFactory.resolve_site_paths_or_raise(tmp_path, config)
>>>>>>> origin/pr/2747
