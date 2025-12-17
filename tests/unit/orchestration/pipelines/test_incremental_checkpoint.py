import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, MagicMock
import json
import os

from egregora.transformations.windowing import (
    save_checkpoint_atomic,
    load_checkpoint,
    Window,
)


class TestAtomicCheckpointSaving:
    """Tests for atomic checkpoint file operations."""

    def test_save_checkpoint_creates_file(self, tmp_path: Path) -> None:
        """Checkpoint file should be created with correct JSON structure."""
        checkpoint_path = tmp_path / ".egregora" / "checkpoint.json"
        timestamp = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        save_checkpoint_atomic(checkpoint_path, timestamp, messages_processed=100)

        assert checkpoint_path.exists()
        data = json.loads(checkpoint_path.read_text())
        assert data["last_processed_timestamp"] == timestamp.isoformat()
        assert data["messages_processed"] == 100
        assert "schema_version" in data

    def test_save_checkpoint_is_atomic(self, tmp_path: Path) -> None:
        """Checkpoint should use temp file + rename for atomicity."""
        checkpoint_path = tmp_path / ".egregora" / "checkpoint.json"
        timestamp = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        # Create initial checkpoint
        save_checkpoint_atomic(checkpoint_path, timestamp, messages_processed=50)

        new_timestamp = datetime(2025, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
        # In a real atomic test we'd try to interrupt, but for unit tests we check the result
        # and assume the implementation uses the correct atomic pattern.
        # We can check that no .tmp file is left behind.
        save_checkpoint_atomic(checkpoint_path, new_timestamp, messages_processed=100)

        assert not (checkpoint_path.with_suffix(".tmp")).exists()
        data = json.loads(checkpoint_path.read_text())
        assert data["messages_processed"] == 100

    def test_save_checkpoint_handles_missing_parent_dir(self, tmp_path: Path) -> None:
        """Checkpoint should create parent directory if missing."""
        checkpoint_path = tmp_path / "nested" / "dir" / "checkpoint.json"
        timestamp = datetime.now(timezone.utc)

        save_checkpoint_atomic(checkpoint_path, timestamp, messages_processed=10)

        assert checkpoint_path.exists()


class TestCheckpointLoadAndTimezone:
    """Tests for loading checkpoints with correct timezone handling."""

    def test_load_checkpoint_returns_utc_datetime(self, tmp_path: Path) -> None:
        """Loaded timestamps must always be timezone-aware UTC."""
        checkpoint_path = tmp_path / "checkpoint.json"
        original_ts = datetime(2025, 6, 15, 14, 30, 0, tzinfo=timezone.utc)

        # We need save_checkpoint_atomic to work for this setup, or we manually write it
        # Since we are TDDing, save_checkpoint_atomic might not exist yet when running this test
        # but the prompt asks to define tests first.
        # Ideally we implement save_checkpoint_atomic right after.

        save_checkpoint_atomic(checkpoint_path, original_ts, messages_processed=50)
        data = load_checkpoint(checkpoint_path)

        loaded_ts = datetime.fromisoformat(data["last_processed_timestamp"])
        assert loaded_ts.tzinfo is not None
        assert loaded_ts == original_ts

    def test_load_checkpoint_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        """Load should return None if checkpoint file doesn't exist."""
        checkpoint_path = tmp_path / "nonexistent.json"
        result = load_checkpoint(checkpoint_path)
        assert result is None


class TestIncrementalCheckpointInPipeline:
    """Tests for checkpoint saving during window processing."""

    @pytest.fixture
    def mock_context(self, tmp_path: Path):
        ctx = MagicMock()
        ctx.config.pipeline.max_windows = None
        ctx.site_root = tmp_path
        # Mock other needed attributes to avoid errors in _process_all_windows
        return ctx

    def test_checkpoint_saved_after_each_window(
        self, monkeypatch, mock_context, tmp_path: Path
    ) -> None:
        """Checkpoint must be saved after each successfully processed window."""
        from egregora.orchestration.pipelines.write import _process_all_windows

        checkpoint_path = tmp_path / ".egregora" / "checkpoint.json"
        now = datetime.now(timezone.utc)
        windows = [
            Window(window_index=i, start_time=now + timedelta(hours=i),
                   end_time=now + timedelta(hours=i+1), table=Mock(), size=10)
            for i in range(3)
        ]

        # Mock dependencies of _process_all_windows
        def mock_process_split(window, *args, **kwargs):
            label = f"window-{window.window_index}"
            return {label: {"posts": ["post-1"]}}

        monkeypatch.setattr(
            "egregora.orchestration.pipelines.write._process_window_with_auto_split",
            mock_process_split
        )
        monkeypatch.setattr("egregora.orchestration.pipelines.write._calculate_max_window_size", lambda config: 100)
        monkeypatch.setattr("egregora.orchestration.pipelines.write._resolve_context_token_limit", lambda config: 100000)
        monkeypatch.setattr("egregora.orchestration.pipelines.write._validate_window_size", lambda window, max_size: None)
        monkeypatch.setattr("egregora.orchestration.pipelines.write._process_background_tasks", lambda ctx: None)

        # NOTE: calling with checkpoint_path, which doesn't exist in signature yet.
        # This will fail until implemented.
        try:
             _process_all_windows(iter(windows), mock_context, checkpoint_path=checkpoint_path)
        except TypeError:
             pytest.fail("Current implementation of _process_all_windows does not accept checkpoint_path")

        assert checkpoint_path.exists()
        data = load_checkpoint(checkpoint_path)
        assert data["messages_processed"] == 3

    def test_checkpoint_preserved_on_failure(
        self, monkeypatch, mock_context, tmp_path: Path
    ) -> None:
        """If window 2 fails, checkpoint from window 1 must still exist."""
        from egregora.orchestration.pipelines.write import _process_all_windows

        checkpoint_path = tmp_path / ".egregora" / "checkpoint.json"
        now = datetime.now(timezone.utc)
        windows = [
            Window(window_index=0, start_time=now, end_time=now + timedelta(hours=1), table=Mock(), size=10),
            Window(window_index=1, start_time=now + timedelta(hours=1), end_time=now + timedelta(hours=2), table=Mock(), size=10),
        ]

        def mock_process(window, *args, **kwargs):
            if window.window_index == 1:
                raise RuntimeError("Simulated failure")
            return {"window_label": {"posts": ["post-1"]}}

        monkeypatch.setattr("egregora.orchestration.pipelines.write._process_window_with_auto_split", mock_process)
        monkeypatch.setattr("egregora.orchestration.pipelines.write._calculate_max_window_size", lambda config: 100)
        monkeypatch.setattr("egregora.orchestration.pipelines.write._resolve_context_token_limit", lambda config: 100000)
        monkeypatch.setattr("egregora.orchestration.pipelines.write._validate_window_size", lambda window, max_size: None)
        monkeypatch.setattr("egregora.orchestration.pipelines.write._process_background_tasks", lambda ctx: None)

        with pytest.raises(RuntimeError, match="Simulated failure"):
            try:
                _process_all_windows(iter(windows), mock_context, checkpoint_path=checkpoint_path)
            except TypeError:
                 pytest.fail("Current implementation of _process_all_windows does not accept checkpoint_path")

        assert checkpoint_path.exists()
        data = load_checkpoint(checkpoint_path)
        assert data["messages_processed"] == 1
