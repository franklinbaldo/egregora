import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
from jules.sprints import SprintManager

class TestSprintManager:
    @pytest.fixture
    def mock_repo_path(self, tmp_path):
        return tmp_path

    def test_init_creates_structure(self, mock_repo_path):
        sprint_mgr = SprintManager(repo_path=mock_repo_path)

        sprints_dir = mock_repo_path / ".jules/sprints"
        current_file = sprints_dir / "current.txt"

        assert sprints_dir.exists()
        assert current_file.exists()
        assert current_file.read_text().strip() == "1"
        assert (sprints_dir / "sprint-1").exists()
        assert (sprints_dir / "sprint-2").exists()
        assert (sprints_dir / "sprint-3").exists()

    def test_get_current_sprint(self, mock_repo_path):
        sprint_mgr = SprintManager(repo_path=mock_repo_path)

        current_file = mock_repo_path / ".jules/sprints/current.txt"
        current_file.write_text("5\n")

        assert sprint_mgr.get_current_sprint() == 5

    def test_increment_sprint(self, mock_repo_path):
        sprint_mgr = SprintManager(repo_path=mock_repo_path)

        # Initial state is 1
        assert sprint_mgr.get_current_sprint() == 1

        # Increment to 2
        new_sprint = sprint_mgr.increment_sprint()

        assert new_sprint == 2
        assert sprint_mgr.get_current_sprint() == 2

        # Check directories created (should create up to sprint-4 now: 2+0, 2+1, 2+2)
        sprints_dir = mock_repo_path / ".jules/sprints"
        assert (sprints_dir / "sprint-4").exists()
        assert (sprints_dir / "sprint-4/README.md").exists()

    def test_get_sprint_context(self, mock_repo_path):
        sprint_mgr = SprintManager(repo_path=mock_repo_path)

        # Create some dummy plans
        sprint_2_dir = mock_repo_path / ".jules/sprints/sprint-2"
        (sprint_2_dir / "refactor-plan.md").touch()

        context = sprint_mgr.get_sprint_context("curator")

        assert "**Current Sprint:** 1" in context
        assert "refactor-plan.md" in context
        assert "curator-feedback.md" in context
