import sys
from pathlib import Path


class TestSchedulerCycle:
    """Tests for the scheduler cycle logic."""

    def test_cycle_waits_for_unknown_mergeability(self, monkeypatch, tmp_path):
        """Verify that the scheduler waits when PR mergeability is UNKNOWN."""
        jules_path = Path(__file__).parents[3] / ".team"
        sys.path.insert(0, str(jules_path))
        try:
            from repo.scheduler.managers import PRManager
        finally:
            sys.path.remove(str(jules_path))

        # Test PRManager.is_green() directly to verify mergeability checks

        pr_manager = PRManager()

        # Case 1: Mergeable is None (UNKNOWN)
        pr_details_unknown = {"number": 123, "mergeable": None, "statusCheckRollup": []}
        assert pr_manager.is_green(pr_details_unknown) is False

        # Case 2: Mergeable is False (CONFLICT)
        pr_details_conflict = {"number": 124, "mergeable": False, "statusCheckRollup": []}
        assert pr_manager.is_green(pr_details_conflict) is False

        # Case 3: Mergeable is True, Check is Pending
        pr_details_pending = {
            "number": 125,
            "mergeable": True,
            "statusCheckRollup": [{"context": "ci/test", "state": "PENDING"}],
        }
        assert pr_manager.is_green(pr_details_pending) is False

        # Case 4: Mergeable is True, Check is Success
        pr_details_success = {
            "number": 126,
            "mergeable": True,
            "statusCheckRollup": [{"context": "ci/test", "state": "SUCCESS"}],
        }
        assert pr_manager.is_green(pr_details_success) is True
