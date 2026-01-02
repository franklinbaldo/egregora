import sys
from pathlib import Path


class TestGithubHelpers:
    def setup_method(self) -> None:
        self.jules_path = Path(__file__).parents[3] / ".jules"
        sys.path.insert(0, str(self.jules_path))
        import jules.github

        self.github = jules.github

    def teardown_method(self) -> None:
        sys.path.remove(str(self.jules_path))
        if "jules.github" in sys.modules:
            del sys.modules["jules.github"]

    def test_last_commit_author_login_prefers_user_login(self) -> None:
        commits = [{"authors": [{"user": {"login": "google-labs-jules[bot]"}}]}]

        login = self.github._get_last_commit_author_login(commits)

        assert login == "google-labs-jules[bot]"

    def test_is_jules_login_matches_known_accounts(self) -> None:
        assert self.github._is_jules_login("google-labs-jules[bot]")
        assert self.github._is_jules_login("app/google-labs-jules")
        assert not self.github._is_jules_login("contributor")
