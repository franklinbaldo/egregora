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

        class DummyClient:
            def list_sessions(self):
                return {
                    "sessions": [
                        {
                            "name": "sessions/123456789012345",
                            "title": "🎭 curator task for repo",
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

        monkeypatch.setattr(scheduler, "ensure_jules_branch_exists", lambda: None)
        monkeypatch.setattr(
            scheduler,
            "prepare_session_base_branch",
            lambda *_args, **_kwargs: "jules-pr42-123456789012345",
        )
        monkeypatch.setattr(
            scheduler,
            "get_pr_by_session_id_any_state",
            lambda *_args: {"number": 42, "mergedAt": "2026-01-05T03:30:00Z"},
        )
        monkeypatch.setattr(scheduler, "get_open_prs", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(scheduler, "JulesClient", lambda: DummyClient())

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
        assert isinstance(created_sessions[0]["branch"], str)
        assert created_sessions[0]["branch"]
