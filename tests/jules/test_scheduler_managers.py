from unittest.mock import MagicMock
from jules.scheduler_managers import CycleStateManager, CycleState
from jules.scheduler_models import PersonaConfig

def test_find_last_cycle_session_critical_bug():
    """
    Test reproducing the critical bug where find_last_cycle_session checks
    baseRefName instead of headRefName for the scheduler prefix.
    """
    # 1. Setup personas
    personas = [
        PersonaConfig(id="persona1", path="p1", emoji="1", prompt_body="", description="d1", journal_entries="j1"),
        PersonaConfig(id="persona2", path="p2", emoji="2", prompt_body="", description="d2", journal_entries="j2"),
    ]
    cycle_mgr = CycleStateManager(personas)

    # 2. Mock JulesClient and list_sessions
    client = MagicMock()
    # Use a format that _extract_session_id recognizes (e.g. 15+ digits)
    session_id = "123456789012345"
    client.list_sessions.return_value = {
        "sessions": [
            {"name": f"projects/p/locations/l/sessions/{session_id}", "createTime": "2023-01-01T00:00:00Z"}
        ]
    }

    # 3. Mock Repo Info
    repo_info = {"owner": "owner", "repo": "repo"}

    # 4. Mock Open PRs
    # The scenario:
    # - PR exists for the session.
    # - headRefName is CORRECT (starts with jules-sched-persona1-...)
    # - baseRefName is "jules" (DOES NOT start with jules-sched)
    #
    # The bug: The code checks baseRefName.startswith("jules-sched"), finds it false, and skips.
    # The expected behavior: It should check headRefName (or just proceed if base is jules),
    # find match, and return the state.

    # Ensure headRefName ends with the session ID so _extract_session_id works
    head_ref = f"jules-sched-persona1-{session_id}"

    open_prs = [
        {
            "number": 100,
            "headRefName": head_ref,  # Correct prefix
            "baseRefName": "jules",                      # Target branch
            "body": f"Session ID: {session_id}",
            "title": "Automated PR"
        }
    ]

    # 5. Call the method
    # Note: we need to ensure JULES_SCHEDULER_PREFIX is imported/used correctly in the module under test.
    state = cycle_mgr.find_last_cycle_session(client, repo_info, open_prs)

    # 6. Assertions
    # If bug exists, it returns a "fresh" state (last_session_id=None)
    # If fixed, it returns state with last_session_id=session_id

    assert state.last_session_id == session_id, \
        f"Bug reproduced: Expected session {session_id}, but got {state.last_session_id}. " \
        "The scheduler likely skipped the PR because it checked baseRefName instead of headRefName."
