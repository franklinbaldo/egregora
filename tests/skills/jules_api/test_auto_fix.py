import sys
from pathlib import Path


class TestAutoFixPrompt:
    def setup_method(self) -> None:
        self.jules_path = Path(__file__).parents[3] / ".jules"
        sys.path.insert(0, str(self.jules_path))
        import jules.auto_fix

        self.auto_fix = jules.auto_fix

    def teardown_method(self) -> None:
        sys.path.remove(str(self.jules_path))
        if "jules.auto_fix" in sys.modules:
            del sys.modules["jules.auto_fix"]

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
