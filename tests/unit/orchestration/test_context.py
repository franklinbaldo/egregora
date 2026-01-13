"""Behavioral tests for pipeline context data structures.

Tests verify the public API and type safety of PipelineContext components.
"""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from egregora.input_adapters.base import AdapterMeta, InputAdapter
from egregora.orchestration.context import PipelineState


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


class TestPipelineStateLibraryTyping:
    """Test that library field accepts ContentLibrary instances."""

    def test_accepts_content_library_instance(self, tmp_path):
        """Should accept ContentLibrary instance for library field."""
        # Mocking ContentLibrary as it's a V3 component
        mock_library = MagicMock(name="ContentLibrary")
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
            library=mock_library,
        )

        assert state.library == mock_library

    def test_accepts_none_for_library(self, tmp_path):
        """Should accept None for library field (lazy initialization)."""
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
            library=None,
        )

        assert state.library is None


class TestPipelineStateInstantiation:
    """Test basic instantiation of PipelineState."""

    def test_instantiation(self, tmp_path):
        """Should instantiate with minimal required fields."""
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
        )
        assert state is not None
