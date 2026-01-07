"""Behavioral tests for pipeline context data structures.

Tests verify the public API and type safety of PipelineContext components.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from google import genai

from egregora.config.settings import EgregoraConfig
from egregora.input_adapters.base import AdapterMeta, InputAdapter
from egregora.orchestration.context import (
    PipelineConfig,
    PipelineContext,
    PipelineState,
)


class MockAdapter(InputAdapter):
    """Mock input adapter for testing."""

    @property
    def source_name(self) -> str:
        return "Mock Source"

    @property
    def source_identifier(self) -> str:
        return "mock"

    def get_adapter_metadata(self) -> AdapterMeta:
        return {
            "name": "Mock",
            "version": "1.0.0",
            "source": "mock",
            "doc_url": "https://example.com",
            "ir_version": "v1",
        }

    def parse(self, input_path: Path, *, timezone: str | None = None, **kwargs):
        pass  # Not needed for type checking


class TestPipelineStateAdapterTyping:
    """Test that adapter field accepts InputAdapter instances."""

    def test_accepts_input_adapter_instance(self, tmp_path):
        """Should accept InputAdapter instance for adapter field."""
        adapter = MockAdapter()
        mock_client = MagicMock()
        mock_storage = MagicMock()
        mock_cache = MagicMock()

        state = PipelineState(
            run_id=uuid4(),
            start_time=datetime.now(UTC),
            source_type="mock",
            input_path=tmp_path / "input.txt",
            client=mock_client,
            storage=mock_storage,
            cache=mock_cache,
            adapter=adapter,  # Should accept InputAdapter
        )

        assert state.adapter == adapter
        assert isinstance(state.adapter, InputAdapter)

    def test_accepts_none_for_adapter(self, tmp_path):
        """Should accept None for adapter field (lazy initialization)."""
        mock_client = MagicMock()
        mock_storage = MagicMock()
        mock_cache = MagicMock()

        state = PipelineState(
            run_id=uuid4(),
            start_time=datetime.now(UTC),
            source_type="mock",
            input_path=tmp_path / "input.txt",
            client=mock_client,
            storage=mock_storage,
            cache=mock_cache,
            adapter=None,  # Should accept None
        )

        assert state.adapter is None


class MockStorage:
    """Mock storage class for testing."""


class MockCache:
    """Mock cache class for testing."""


@pytest.fixture
def mock_config(config_factory) -> EgregoraConfig:
    """Fixture for EgregoraConfig."""
    return config_factory()


@pytest.fixture
def mock_pipeline_config(tmp_path: Path, mock_config: EgregoraConfig) -> PipelineConfig:
    """Fixture for PipelineConfig."""
    return PipelineConfig(
        config=mock_config,
        output_dir=tmp_path,
        site_root=tmp_path,
        docs_dir=tmp_path / "docs",
        posts_dir=tmp_path / "docs" / "posts",
        profiles_dir=tmp_path / "docs" / "profiles",
        media_dir=tmp_path / "docs" / "media",
    )


@pytest.fixture
def mock_pipeline_state(tmp_path: Path) -> PipelineState:
    """Fixture for PipelineState."""
    return PipelineState(
        run_id=uuid4(),
        start_time=datetime.now(UTC),
        source_type="test_source",
        input_path=tmp_path / "input.zip",
        client=genai.Client(),
        storage=MockStorage(),
        cache=MockCache(),
    )


def test_pipeline_context_instantiation_and_property_access(
    mock_pipeline_config: PipelineConfig, mock_pipeline_state: PipelineState
):
    """Tests that PipelineContext can be instantiated and its properties accessed."""
    context = PipelineContext(config_obj=mock_pipeline_config, state=mock_pipeline_state)

    # Test property forwarding from state
    assert context.run_id == mock_pipeline_state.run_id
    assert context.client == mock_pipeline_state.client

    # Test property forwarding from config
    assert context.output_dir == mock_pipeline_config.output_dir
    assert context.writer_model == mock_pipeline_config.writer_model
    assert context.config == mock_pipeline_config.config

    # Test a few properties to ensure they don't raise errors
    assert context.start_time is not None
    assert context.source_type == "test_source"
    assert context.posts_dir.name == "posts"
    assert context.enable_rag is True
