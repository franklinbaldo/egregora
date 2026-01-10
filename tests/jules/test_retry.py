import subprocess
import pytest
from unittest.mock import MagicMock, patch
from jules.scheduler_managers import PRManager
from jules.exceptions import MergeError

def test_merge_into_jules_retry():
    pr_mgr = PRManager()

    # We want to verify that _merge_with_retry is called and retries on failure.
    # However, testing retry decorators is tricky with mocks if we don't mock the internal call.
    # Instead, we will simulate the behavior by patching subprocess.run.

    with patch("subprocess.run") as mock_run:
        # Side effect:
        # 1. retarget -> Success
        # 2. merge -> Fail (CalledProcessError)
        # 3. merge -> Fail
        # 4. merge -> Success

        # NOTE: tenacity might not retry if we patch at this level if it wraps the method itself.
        # But we want to test that `merge_into_jules` handles the retries via `_merge_with_retry`.

        # If we just test `merge_into_jules`, we need to make sure the mocked subprocess.run
        # behaves as expected across calls.

        # Calls:
        # 1. gh pr edit ... (success)
        # 2. gh pr merge ... (fail)
        # 3. gh pr merge ... (fail)
        # 4. gh pr merge ... (success)
        # 5. git push ... (delete branch - optional)

        fail_error = subprocess.CalledProcessError(1, ["gh", "pr", "merge"], stderr=b"Transient error")

        def side_effect(cmd, **kwargs):
            if "edit" in cmd:
                return MagicMock(stdout=b"Retargeted")
            if "merge" in cmd:
                side_effect.merge_calls += 1
                if side_effect.merge_calls < 3:
                    raise fail_error
                return MagicMock(stdout=b"Merged")
            if "view" in cmd:
                 return MagicMock(stdout=b"branch-name")
            if "push" in cmd: # delete branch
                return MagicMock(stdout=b"Deleted")
            return MagicMock()

        side_effect.merge_calls = 0
        mock_run.side_effect = side_effect

        # Because tenacity waits, we want to mock time.sleep or configure tenacity to not wait in tests.
        # But for this test, let's just assert that it eventually succeeds.
        # To avoid slow tests, we should probably mock the wait.

        # Actually, since `_merge_with_retry` is decorated, we can mock it directly to verify it was called,
        # OR we can verify retry behavior. Testing retry behavior with sleep is slow.
        # Ideally we'd replace the retry strategy.

        pr_mgr.merge_into_jules(123)

        assert side_effect.merge_calls == 3
        # Ensure retarget was called
        mock_run.assert_any_call(["gh", "pr", "edit", "123", "--base", "jules"], check=True, capture_output=True)
