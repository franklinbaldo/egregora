import sys
from pathlib import Path


class TestAutoFixPrompt:
    def setup_method(self) -> None:
        self.team_path = Path(__file__).parents[3] / ".team"
        sys.path.insert(0, str(self.team_path))
        from repo.features import autofix as auto_fix

        self.auto_fix = auto_fix

    def teardown_method(self) -> None:
        sys.path.remove(str(self.team_path))
        if "repo.features.autofix" in sys.modules:
            del sys.modules["repo.features.autofix"]

    def test_render_feedback_prompt_includes_ci_logs(self) -> None:
        details = {
            "failed_check_names": ["lint", "tests"],
            "has_conflicts": False,
        }
        prompt = self.auto_fix._render_feedback_prompt(
            pr_number=42,
            details=details,
            logs_summary="lint failed on step build",
            full_ci_logs="Job: lint\nStep: build\nLogs content...",
        )

        assert "lint failed on step build" in prompt
        assert "Job: lint" in prompt
        assert "CI Failures" in prompt

    def test_creates_new_session_when_latest_commit_not_from_jules(self, monkeypatch) -> None:
        created_sessions: list[dict] = []
        sent_messages: list[str] = []
        fetched_sessions: list[str] = []

        class DummyClient:
            def create_session(
                self,
                prompt: str,
                owner: str,
                repo: str,
                branch: str = "main",
                title: str | None = None,
                *,
                require_plan_approval: bool = False,
                automation_mode: str = "AUTO_CREATE_PR",
            ):
                created_sessions.append(
                    {
                        "prompt": prompt,
                        "owner": owner,
                        "repo": repo,
                        "branch": branch,
                        "title": title,
                        "require_plan_approval": require_plan_approval,
                        "automation_mode": automation_mode,
                    }
                )
                return {"name": "sessions/123456789"}

            def get_session(self, session_id: str):
                fetched_sessions.append(session_id)
                return {"state": "ACTIVE"}

            def send_message(self, session_id: str, message: str):
                sent_messages.append(message)
                return {}

        monkeypatch.setattr(self.auto_fix, "TeamClient", lambda: DummyClient())
        monkeypatch.setattr(self.auto_fix, "get_repo_info", lambda: {"repo_full": "owner/repo"})
        monkeypatch.setattr(self.auto_fix, "get_base_sha", lambda *_args, **_kwargs: "base-sha")
        monkeypatch.setattr(self.auto_fix, "fetch_failed_logs_summary", lambda *_args, **_kwargs: "")
        monkeypatch.setattr(self.auto_fix, "fetch_full_ci_logs", lambda **_kwargs: "")
        monkeypatch.setattr(
            self.auto_fix,
            "get_pr_details_via_gh",
            lambda _pr_number, **_kwargs: {
                "session_id": "existing-session",
                "last_commit_by_jules": False,
                "last_commit_author_login": "contributor",
                "branch": "feature/test-branch",
                "base_branch": "main",
                "title": "Fix things",
                "body": "Body",
                "changed_files": ["file.py"],
                "passed_all_checks": False,
                "has_conflicts": False,
                "failed_check_names": ["lint"],
            },
        )
        monkeypatch.setattr(self.auto_fix, "_render_feedback_prompt", lambda **_kwargs: "feedback")
        monkeypatch.setattr(self.auto_fix, "post_pr_comment", lambda *_args, **_kwargs: None)

        result = self.auto_fix.auto_reply_to_jules(7)

        assert result["action"] == "created_new_session"
        assert created_sessions
        assert created_sessions[0]["automation_mode"] == self.auto_fix.AUTOFIX_AUTOMATION_MODE
        assert fetched_sessions == []
        assert sent_messages == []

    def test_reuses_session_when_latest_commit_from_jules(self, monkeypatch) -> None:
        created_sessions: list[dict] = []
        sent_messages: list[tuple[str, str]] = []
        fetched_sessions: list[str] = []

        class DummyClient:
            def create_session(self, *args, **kwargs):
                created_sessions.append({"args": args, "kwargs": kwargs})
                return {"name": "sessions/new"}

            def get_session(self, session_id: str):
                fetched_sessions.append(session_id)
                return {"state": "ACTIVE"}

            def send_message(self, session_id: str, message: str):
                sent_messages.append((session_id, message))
                return {}

        monkeypatch.setattr(self.auto_fix, "TeamClient", lambda: DummyClient())
        monkeypatch.setattr(self.auto_fix, "get_repo_info", lambda: {"repo_full": "owner/repo"})
        monkeypatch.setattr(self.auto_fix, "fetch_failed_logs_summary", lambda *_args, **_kwargs: "")
        monkeypatch.setattr(self.auto_fix, "fetch_full_ci_logs", lambda **_kwargs: "")
        monkeypatch.setattr(
            self.auto_fix,
            "get_pr_details_via_gh",
            lambda _pr_number, **_kwargs: {
                "session_id": "existing-session",
                "last_commit_by_jules": True,
                "last_commit_author_login": "google-labs-jules[bot]",
                "branch": "feature/test-branch",
                "base_branch": "main",
                "title": "Fix things",
                "body": "Body",
                "changed_files": ["file.py"],
                "passed_all_checks": False,
                "has_conflicts": False,
                "failed_check_names": ["lint"],
            },
        )
        monkeypatch.setattr(self.auto_fix, "_render_feedback_prompt", lambda **_kwargs: "feedback")
        monkeypatch.setattr(self.auto_fix, "post_pr_comment", lambda *_args, **_kwargs: None)

        result = self.auto_fix.auto_reply_to_jules(9)

        assert result["action"] == "messaged_existing_session"
        assert created_sessions == []
        assert fetched_sessions == ["existing-session"]
        assert sent_messages
        assert sent_messages[0][0] == "existing-session"
        assert "feedback" in sent_messages[0][1]
