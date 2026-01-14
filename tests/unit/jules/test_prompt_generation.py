import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock
from jules.scheduler.loader import PersonaLoader

class TestPromptGeneration(unittest.TestCase):
    def setUp(self):
        # We don't really need setup if we init per test with correct root
        pass

    def test_password_injection_and_template(self):
        # We want to test that _render_prompt injects password and the template renders it.
        # We can use the actual template file from disk?
        # Construct a loader that points to repo root .jules
        repo_root = Path(".").resolve() / ".jules"
        loader = PersonaLoader(repo_root / "personas", base_context={})
        
        metadata = {"id": "test-persona", "emoji": "🤖"}
        context = {"description": "A test bot", "journal_entries": ""}
        
        # Test the template rendering
        # We need to manually invoke _render_prompt with the content of persona.md.j2
        template_path = repo_root / "jules/templates/base/persona.md.j2"
        if not template_path.exists():
            print(f"Template not found at {template_path}")
            return
            
        template_content = template_path.read_text()
        
        # Mock sprint_manager to avoid error
        with unittest.mock.patch("jules.features.sprints.sprint_manager") as mock_sm:
            mock_sm.get_sprint_context.return_value = "Sprint Context"
            
            rendered = loader._render_prompt(template_content, metadata, context)
            
            # Verify Password Injection
            expected_pass = str(uuid.uuid5(uuid.NAMESPACE_DNS, "test-persona"))
            self.assertIn(expected_pass, rendered)
            
            # Verify Job Instructions
            self.assertIn("my-tools login", rendered)
            self.assertIn("Execute assigned tasks", rendered)
            self.assertIn("my-tools email inbox", rendered)

if __name__ == "__main__":
    unittest.main()
