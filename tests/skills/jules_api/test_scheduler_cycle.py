import sys
from pathlib import Path


class TestSchedulerCycleFallback:
    def test_cycle_uses_merged_pr_and_moves_to_next_persona(self, monkeypatch, tmp_path):
        jules_path = Path(__file__).parents[3] / ".jules"
        sys.path.insert(0, str(jules_path))
        try:
            import jules.scheduler
        finally:
            sys.path.remove(str(jules_path))

        scheduler = jules.scheduler

        created_sessions: list[dict] = []
        history_appends: list[tuple[str, str]] = []
        commit_history_calls: list[str] = []

        class DummyHistoryManager:
            def __init__(self, *_args, **_kwargs):
                pass

            def get_last_entry(self):
                return {
                    "session_id": "123456789012345",
                    "persona": "curator",
                    "base_branch": "jules",
                    "base_pr_number": "",
                }

            def append_entry(
                self, session_id: str, persona: str, _base_branch: str, _base_pr_number: str = ""
            ):
                history_appends.append((session_id, persona))

            def commit_history(self):
                commit_history_calls.append("commit")

        class DummyClient:
            def create_session(self, **kwargs):
                created_sessions.append(kwargs)
                return {"name": "sessions/new-session-id"}

        prompt_dir = tmp_path / "curator"
        prompt_dir.mkdir()
        prompt_file = prompt_dir / "prompt.md"
        prompt_file.write_text(
            "---\nid: curator\nemoji: 🎭\ntitle: Curator Task\n---\n\nDo curator things.\n"
        )

        monkeypatch.setattr(scheduler, "HistoryManager", DummyHistoryManager)
        monkeypatch.setattr(scheduler, "ensure_jules_branch_exists", lambda: None)
        monkeypatch.setattr(
            scheduler,
            "get_pr_by_session_id_any_state",
            lambda *_args: {"number": 42, "mergedAt": "2026-01-05T03:30:00Z"},
        )
        monkeypatch.setattr(scheduler, "get_open_prs", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(scheduler, "JulesClient", lambda: DummyClient())

        repo_info = {"owner": "owner", "repo": "repo"}
        personas = {
            "curator": {
                "path": prompt_file,
                "id": "curator",
                "emoji": "🎭",
                "title": "Curator Task",
            },
            "builder": {
                "path": prompt_file,
                "id": "builder",
                "emoji": "🏗️",
                "title": "Builder Task",
            },
        }

        cycle_list = ["curator", "builder"]
        base_context = {"open_prs": []}

        scheduler.run_cycle_step(
            client=DummyClient(),
            repo_info=repo_info,
            cycle_list=cycle_list,
            personas=personas,
            open_prs=[],
            dry_run=False,
            base_context=base_context,
        )

        assert created_sessions, "Scheduler should start the next persona session after merged PR."
        assert created_sessions[0]["branch"] == scheduler.JULES_BRANCH
        assert history_appends == [("new-session-id", "builder")]
        assert commit_history_calls == ["commit"]
