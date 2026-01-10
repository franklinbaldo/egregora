import json
from jules.reconciliation_tracker import ReconciliationTracker

def test_tracker_lifecycle(tmp_path):
    # Setup
    state_file = tmp_path / "state/reconciliation.json"

    class TestTracker(ReconciliationTracker):
        STATE_FILE = state_file

    tracker = TestTracker()

    # 1. Initial state
    assert tracker.is_reconciliation_active(1) is False

    # 2. Mark active
    tracker.mark_reconciliation_active(1, "sess1", 100)
    assert tracker.is_reconciliation_active(1) is True
    assert tracker.is_reconciliation_active(2) is False

    # Verify file content
    content = json.loads(state_file.read_text())
    assert content["sprint"] == 1
    assert content["session_id"] == "sess1"
    assert content["status"] == "active"

    # 3. Mark complete
    tracker.mark_reconciliation_complete()
    assert tracker.is_reconciliation_active(1) is False

    # Verify file content
    content = json.loads(state_file.read_text())
    assert content["status"] == "completed"
    assert "completed_at" in content
