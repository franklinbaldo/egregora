"""Tests for orchestration.write_pipeline run refactor."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from egregora.config.settings import EgregoraConfig
from egregora.orchestration import write_pipeline
from egregora.orchestration.write_pipeline import PreprocessingArtifacts


class NamedClosable:
    """Test helper that tracks whether ``close`` was invoked."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.closed = False

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def site_paths(tmp_path: Path) -> SimpleNamespace:
    """Provide minimal site paths structure for tests."""

    posts_dir = tmp_path / "posts"
    profiles_dir = tmp_path / "profiles"
    media_dir = tmp_path / "media"
    docs_dir = tmp_path / "docs"
    rag_dir = tmp_path / "rag"
    for directory in (posts_dir, profiles_dir, media_dir, docs_dir, rag_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return SimpleNamespace(
        site_root=tmp_path,
        mkdocs_path=tmp_path / "mkdocs.yml",
        docs_dir=docs_dir,
        profiles_dir=profiles_dir,
        posts_dir=posts_dir,
        media_dir=media_dir,
        rag_dir=rag_dir,
    )


@pytest.fixture(autouse=True)
def _create_mkdocs_config(site_paths: SimpleNamespace) -> None:
    """Ensure mkdocs.yml exists for environment validation."""

    site_paths.mkdocs_path.write_text("site_name: test\n", encoding="utf-8")


def _stub_setup_pipeline_environment(
    site_paths: SimpleNamespace,
    created_clients: list[NamedClosable],
):
    """Build a stub for ``_setup_pipeline_environment``."""

    def _stub(
        output_dir: Path,
        _config: EgregoraConfig,
        _api_key: str | None,
        model_override: str | None,
        client: NamedClosable | None,
    ) -> tuple[
        SimpleNamespace,
        str,
        NamedClosable,
        NamedClosable,
        str | None,
        NamedClosable,
        NamedClosable,
    ]:
        backend = NamedClosable("backend")
        runs_backend = NamedClosable("runs")
        cache = NamedClosable("cache")
        resolved_client = client
        if resolved_client is None:
            resolved_client = NamedClosable("client")
            created_clients.append(resolved_client)
        return (
            site_paths,
            "duckdb:///tmp",  # runtime_db_uri placeholder
            backend,
            runs_backend,
            model_override,
            resolved_client,
            cache,
        )

    return _stub


def _stub_get_adapter(source: str) -> SimpleNamespace:
    return SimpleNamespace(source_name=source)


def test_run_closes_managed_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, site_paths: SimpleNamespace) -> None:
    """When run manages the client lifecycle it should close it on exit."""

    created_clients: list[NamedClosable] = []
    monkeypatch.setattr(write_pipeline, "get_adapter", _stub_get_adapter)
    monkeypatch.setattr(
        write_pipeline,
        "_setup_pipeline_environment",
        _stub_setup_pipeline_environment(site_paths, created_clients),
    )

    captured_env: dict[str, write_pipeline.PipelineEnvironment] = {}

    def preprocess_stub(
        env: write_pipeline.PipelineEnvironment,
        input_path: Path,
        output_dir: Path,
        config: EgregoraConfig,
    ) -> PreprocessingArtifacts:
        captured_env["env"] = env
        return PreprocessingArtifacts(
            messages_table=object(),
            windows_iterator=[],
            window_ctx_kwargs={},
            output_format=object(),
            checkpoint_path=tmp_path / "checkpoint.json",
            enable_enrichment=False,
            embedding_model="embed",
        )

    monkeypatch.setattr(write_pipeline, "_preprocess_messages", preprocess_stub)

    execution_calls: list[tuple] = []

    def execute_stub(
        preprocessed: PreprocessingArtifacts,
        runs_backend: NamedClosable,
        site_paths_arg: SimpleNamespace,
        config: EgregoraConfig,
    ) -> dict[str, dict[str, list[str]]]:
        execution_calls.append((preprocessed, runs_backend, site_paths_arg, config))
        return {"result": {}}

    monkeypatch.setattr(write_pipeline, "_execute_windows_and_finalize", execute_stub)

    result = write_pipeline.run(
        source="whatsapp",
        input_path=tmp_path / "input.zip",
        output_dir=tmp_path,
        config=EgregoraConfig(),
    )

    assert result == {"result": {}}
    assert execution_calls, "execution helper should be invoked"
    env = captured_env["env"]
    assert created_clients and created_clients[0].closed, "managed client must be closed"
    assert env.enrichment_cache.closed
    assert env.runs_backend.closed
    assert env.backend.closed


def test_run_preserves_provided_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, site_paths: SimpleNamespace) -> None:
    """Caller-supplied client should not be closed by the pipeline."""

    monkeypatch.setattr(write_pipeline, "get_adapter", _stub_get_adapter)
    created_clients: list[NamedClosable] = []
    monkeypatch.setattr(
        write_pipeline,
        "_setup_pipeline_environment",
        _stub_setup_pipeline_environment(site_paths, created_clients),
    )

    provided_client = NamedClosable("external-client")

    def preprocess_stub(
        env: write_pipeline.PipelineEnvironment,
        input_path: Path,
        output_dir: Path,
        config: EgregoraConfig,
    ) -> PreprocessingArtifacts:
        assert env.client is provided_client
        return PreprocessingArtifacts(
            messages_table=object(),
            windows_iterator=[],
            window_ctx_kwargs={},
            output_format=object(),
            checkpoint_path=tmp_path / "checkpoint.json",
            enable_enrichment=False,
            embedding_model="embed",
        )

    monkeypatch.setattr(write_pipeline, "_preprocess_messages", preprocess_stub)

    monkeypatch.setattr(
        write_pipeline,
        "_execute_windows_and_finalize",
        lambda preprocessed, runs_backend, site_paths_arg, config: {"ok": True},
    )

    result = write_pipeline.run(
        source="whatsapp",
        input_path=tmp_path / "input.zip",
        output_dir=tmp_path,
        config=EgregoraConfig(),
        client=provided_client,
    )

    assert result == {"ok": True}
    assert not created_clients, "no new client should be created when one is supplied"
    assert not provided_client.closed, "provided client must remain open"


def test_setup_pipeline_environment_reuses_existing_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, site_paths: SimpleNamespace
) -> None:
    """``_setup_pipeline_environment`` should reuse supplied clients and avoid new instantiation."""

    monkeypatch.setattr(
        write_pipeline,
        "_resolve_pipeline_site_paths",
        lambda output_dir, config: site_paths,
    )
    monkeypatch.setattr(
        write_pipeline,
        "_create_database_backends",
        lambda _site_root, _config: ("runtime", NamedClosable("backend"), NamedClosable("runs")),
    )

    class DummyCache(NamedClosable):
        def __init__(self, directory: Path) -> None:  # pragma: no cover - simple delegation
            super().__init__("cache")
            self.directory = directory

    monkeypatch.setattr(write_pipeline, "EnrichmentCache", DummyCache)

    def fail_client(*_args, **_kwargs):  # pragma: no cover - ensures we do not create new clients
        raise AssertionError("genai.Client should not be constructed when client is provided")

    monkeypatch.setattr(write_pipeline.genai, "Client", fail_client)

    config = EgregoraConfig()
    existing_client = NamedClosable("external")

    (
        resolved_site_paths,
        runtime_db_uri,
        backend,
        runs_backend,
        model_override,
        returned_client,
        cache,
    ) = write_pipeline._setup_pipeline_environment(
        tmp_path,
        config,
        api_key="key",
        model_override="override",
        client=existing_client,
    )

    assert resolved_site_paths is site_paths
    assert runtime_db_uri == "runtime"
    assert isinstance(backend, NamedClosable)
    assert isinstance(runs_backend, NamedClosable)
    assert model_override == "override"
    assert returned_client is existing_client
    assert isinstance(cache, DummyCache)
    assert cache.directory.name == site_paths.site_root.name

