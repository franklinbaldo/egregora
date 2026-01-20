import sys
from pathlib import Path


class TestSchedulerCycleFallback:
    """Tests for the scheduler cycle logic, including fallback mechanisms."""

    def test_cycle_uses_merged_pr_and_moves_to_next_persona(self, monkeypatch, tmp_path):
        jules_path = Path(__file__).parents[3] / ".team"
        sys.path.insert(0, str(jules_path))
        try:
            import repo.scheduler
            import repo.scheduler_legacy
        finally:
            sys.path.remove(str(jules_path))

        scheduler = repo.scheduler
        scheduler_legacy = repo.scheduler_legacy

        created_sessions: list[dict] = []

        class DummyClient:
            def list_sessions(self):
                return {
                    "sessions": [
                        {
                            "name": "sessions/123456789012345",
                            "createTime": "2026-01-05T03:30:00Z",
                        }
                    ]
                }

            def create_session(self, **kwargs):
                created_sessions.append(kwargs)
                return {"name": "sessions/new-session-id"}

        curator_dir = tmp_path / "curator"
        curator_dir.mkdir()
        curator_prompt = curator_dir / "prompt.md"
        curator_prompt.write_text(
            "---\nid: curator\nemoji: 🎭\ntitle: Curator Task\n---\n\nDo curator things.\n"
        )
        builder_dir = tmp_path / "builder"
        builder_dir.mkdir()
        builder_prompt = builder_dir / "prompt.md"
        builder_prompt.write_text(
            "---\nid: builder\nemoji: 🏗️\ntitle: Builder Task\n---\n\nDo builder things.\n"
        )

        # Mock on both scheduler and scheduler_legacy modules
        monkeypatch.setattr(scheduler, "ensure_scheduled_branch_exists", lambda: None)
        monkeypatch.setattr(scheduler_legacy, "ensure_scheduled_branch_exists", lambda: None)
        monkeypatch.setattr(
            scheduler,
            "prepare_session_base_branch",
            lambda *_args, **_kwargs: "jules-sched-builder-pr42",
        )
        monkeypatch.setattr(
            scheduler_legacy,
            "prepare_session_base_branch",
            lambda *_args, **_kwargs: "jules-sched-builder-pr42",
        )
        monkeypatch.setattr(
            scheduler,
            "get_pr_by_session_id_any_state",
            lambda *_args: {
                "number": 42,
                "mergedAt": "2026-01-05T03:30:00Z",
                "headRefName": "jules-sched-curator-pr42-123456789012345",
                "baseRefName": "jules-sched-curator-pr42",
            },
        )
        monkeypatch.setattr(
            scheduler_legacy,
            "get_pr_by_session_id_any_state",
            lambda *_args: {
                "number": 42,
                "mergedAt": "2026-01-05T03:30:00Z",
                "headRefName": "jules-sched-curator-pr42-123456789012345",
                "baseRefName": "jules-sched-curator-pr42",
            },
        )
        monkeypatch.setattr(scheduler, "get_open_prs", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(scheduler_legacy, "get_open_prs", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(scheduler, "TeamClient", lambda: DummyClient())
        monkeypatch.setattr(scheduler_legacy, "TeamClient", lambda: DummyClient())

        repo_info = {"owner": "owner", "repo": "repo"}
        cycle_entries = [
            {"id": "curator", "path": curator_prompt},
            {"id": "builder", "path": builder_prompt},
        ]
        base_context = {"open_prs": []}

        scheduler.run_cycle_step(
            client=DummyClient(),
            repo_info=repo_info,
            cycle_entries=cycle_entries,
            open_prs=[],
            dry_run=False,
            base_context=base_context,
        )

        assert created_sessions, "Scheduler should start the next persona session after merged PR."
        assert created_sessions[0]["branch"] == "jules-sched-builder-pr42"

    def test_cycle_uses_session_starting_branch_when_prs_unavailable(self, monkeypatch, tmp_path):
        jules_path = Path(__file__).parents[3] / ".team"
        sys.path.insert(0, str(jules_path))
        try:
            import repo.scheduler
        finally:
            sys.path.remove(str(jules_path))

        scheduler = repo.scheduler
        created_sessions: list[dict] = []
        seen_session_ids: list[str] = []

        class DummyClient:
            def list_sessions(self):
                return {
                    "sessions": [
                        {
                            "name": "sessions/999999999999999",
                            "createTime": "2026-01-05T03:30:00Z",
                            "sourceContext": {
                                "githubRepoContext": {
                                    "startingBranch": "jules-sched-refactor-main-202601010000"
                                }
                            },
                        }
                    ]
                }

            def get_session(self, session_id):
                seen_session_ids.append(session_id)
                return {"state": "RUNNING"}

            def create_session(self, **kwargs):
                created_sessions.append(kwargs)
                return {"name": "sessions/new-session-id"}

        refactor_dir = tmp_path / "refactor"
        refactor_dir.mkdir()
        refactor_prompt = refactor_dir / "prompt.md"
        refactor_prompt.write_text(
            "---\nid: refactor\nemoji: 🔧\ntitle: Refactor Task\n---\n\nDo refactor things.\n"
        )
        curator_dir = tmp_path / "curator"
        curator_dir.mkdir()
        curator_prompt = curator_dir / "prompt.md"
        curator_prompt.write_text(
            "---\nid: curator\nemoji: 🎭\ntitle: Curator Task\n---\n\nDo curator things.\n"
        )

        monkeypatch.setattr(scheduler, "ensure_scheduled_branch_exists", lambda: None)
        monkeypatch.setattr(scheduler, "get_pr_by_session_id_any_state", lambda *_args: None)
        monkeypatch.setattr(scheduler, "get_open_prs", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(scheduler, "TeamClient", lambda: DummyClient())

        repo_info = {"owner": "owner", "repo": "repo"}
        cycle_entries = [
            {"id": "curator", "path": curator_prompt},
            {"id": "refactor", "path": refactor_prompt},
        ]
        base_context = {"open_prs": []}

        scheduler.run_cycle_step(
            client=DummyClient(),
            repo_info=repo_info,
            cycle_entries=cycle_entries,
            open_prs=[],
            dry_run=False,
            base_context=base_context,
        )

        assert created_sessions == [], "Scheduler should not restart cycle when a scheduler session exists."
        assert seen_session_ids == ["999999999999999"]

    def test_cycle_waits_for_unknown_mergeability(self, monkeypatch, tmp_path):
        """Verify that the scheduler waits when PR mergeability is UNKNOWN."""
        jules_path = Path(__file__).parents[3] / ".team"
        sys.path.insert(0, str(jules_path))
        try:
            import repo.scheduler_managers
            import repo.scheduler_state
            import repo.scheduler_v2
        finally:
            sys.path.remove(str(jules_path))

        # We need to test execute_cycle_tick from scheduler_v2, or directly call PRManager
        # Since the legacy scheduler.run_cycle_step doesn't use PRManager, we should test PRManager directly
        # or test execute_cycle_tick. Given existing tests focus on scheduler_legacy (run_cycle_step),
        # but I updated scheduler_managers.py, I should test PRManager directly here to verify my changes.

        pr_manager = repo.scheduler_managers.PRManager()

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
