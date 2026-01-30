import sys
from pathlib import Path


class TestGithubHelpers:
    def setup_method(self) -> None:
        self.team_path = Path(__file__).parents[3] / ".team"
        sys.path.insert(0, str(self.team_path))
        from repo.core import github

        self.github = github

    def teardown_method(self) -> None:
        sys.path.remove(str(self.team_path))
        if "repo.core.github" in sys.modules:
            del sys.modules["repo.core.github"]

    def test_last_commit_author_login_prefers_user_login(self) -> None:
        commits = [{"authors": [{"user": {"login": "google-labs-jules[bot]"}}]}]

        login = self.github._get_last_commit_author_login(commits)

        assert login == "google-labs-jules[bot]"

    def test_is_jules_login_matches_known_accounts(self) -> None:
        assert self.github._is_jules_login("google-labs-jules[bot]")
        assert self.github._is_jules_login("app/google-labs-jules")
        assert not self.github._is_jules_login("contributor")
