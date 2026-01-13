"""Test the parallel scheduler logic (TDD)."""

import pytest
from pathlib import Path
from dataclasses import asdict
import json
import tomllib
from unittest.mock import Mock, patch

from jules.scheduler_models import CycleState
from jules.scheduler_state import PersistentCycleState
from jules.scheduler_managers import CycleStateManager

class TestParallelScheduler:
    @pytest.fixture
    def mock_schedules_toml(self, tmp_path):
        content = """
        [tracks]
        product = ["visionary", "forge", "refactor"]
        maintenance = ["janitor", "pruner", "shepherd"]
        quality = ["curator", "sentinel", "docs_curator"]
        """
        f = tmp_path / "schedules.toml"
        f.write_text(content)
        return f

    @pytest.fixture
    def mock_cycle_state_json(self, tmp_path):
        f = tmp_path / "cycle_state.json"
        return f

    def test_load_tracks_from_toml(self, mock_schedules_toml):
        """Verify we can parse [tracks] from TOML."""
        with open(mock_schedules_toml, "rb") as f:
            data = tomllib.load(f)

        tracks = data.get("tracks")
        assert tracks is not None
        assert "product" in tracks
        assert "maintenance" in tracks
        assert tracks["product"] == ["visionary", "forge", "refactor"]

    def test_persistent_state_supports_tracks(self, mock_cycle_state_json):
        """Verify PersistentCycleState can store state per track."""
        state = PersistentCycleState()

        # Record session on a track
        state.record_session(
            persona_id="forge",
            persona_index=1,
            session_id="session-123",
            track_name="product"
        )

        # Verify track state
        track = state.get_track("product")
        assert track.last_persona_id == "forge"
        assert track.last_session_id == "session-123"

        # Save and Load
        state.save(mock_cycle_state_json)
        loaded_state = PersistentCycleState.load(mock_cycle_state_json)

        assert "product" in loaded_state.tracks
        assert loaded_state.tracks["product"].last_persona_id == "forge"

    def test_cycle_state_manager_advances_track(self):
        """Verify CycleStateManager can advance a specific track."""
        # Setup manager with a track
        track_personas = [Mock(id="p1"), Mock(id="p2"), Mock(id="p3")]
        manager = CycleStateManager(cycle_personas=track_personas) # Legacy init

        # Test advance logic (existing logic handles list index)
        next_idx, increment = manager.advance_cycle("p1")
        assert next_idx == 1 # p2
        assert increment is False

        next_idx, increment = manager.advance_cycle("p3")
        assert next_idx == 0 # p1
        assert increment is True
