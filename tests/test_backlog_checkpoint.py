"""Tests for checkpoint persistence utilities."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.backlog.checkpoint import CheckpointManager, CheckpointState


def test_checkpoint_saves_and_loads(tmp_path: Path) -> None:
    checkpoint_file = tmp_path / "checkpoint.json"
    manager = CheckpointManager(checkpoint_file, backup=False)

    state = CheckpointState(last_processed_date="2024-10-01", total_processed=5)
    manager.save(state)

    loaded = manager.load()
    assert loaded.last_processed_date == "2024-10-01"
    assert loaded.total_processed == 5


def test_checkpoint_updates_timestamps(tmp_path: Path) -> None:
    checkpoint_file = tmp_path / "checkpoint.json"
    manager = CheckpointManager(checkpoint_file, backup=False)

    state = CheckpointState()
    assert state.started_at is None
    manager.save(state)
    assert state.started_at is not None
    assert state.last_updated is not None


def test_checkpoint_handles_corrupted_file(tmp_path: Path) -> None:
    checkpoint_file = tmp_path / "checkpoint.json"
    checkpoint_file.write_text("not-json", encoding="utf-8")

    manager = CheckpointManager(checkpoint_file, backup=False)
    state = manager.load()
    assert state.last_processed_date is None
    assert checkpoint_file.exists() is False


def test_checkpoint_creates_backup(tmp_path: Path) -> None:
    checkpoint_file = tmp_path / "checkpoint.json"
    manager = CheckpointManager(checkpoint_file, backup=True)

    state = CheckpointState(last_processed_date="2024-10-01")
    manager.save(state)

    state2 = CheckpointState(last_processed_date="2024-10-02")
    manager.save(state2)

    assert checkpoint_file.with_suffix(".json.bak").exists()


def test_checkpoint_roundtrip_statistics(tmp_path: Path) -> None:
    checkpoint_file = tmp_path / "checkpoint.json"
    manager = CheckpointManager(checkpoint_file, backup=False)

    state = CheckpointState(
        last_processed_date="2024-10-01",
        statistics={"total_messages": 100, "estimated_cost_usd": 1.5},
    )
    manager.save(state)

    loaded = manager.load()
    assert loaded.statistics["total_messages"] == 100
    assert loaded.statistics["estimated_cost_usd"] == 1.5
