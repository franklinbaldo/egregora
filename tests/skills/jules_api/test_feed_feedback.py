import sys
import unittest
from pathlib import Path


class TestFeedFeedback(unittest.TestCase):
    def setUp(self):
        """Set up test environment by modifying sys.path to import the script."""
        self.skills_path = str(
            Path(__file__).parent.parent.parent.parent / ".claude" / "skills" / "jules-api"
        )
        sys.path.insert(0, self.skills_path)
        # Dynamically import the module under test now that the path is set
        import feed_feedback

        self.feed_feedback = feed_feedback

    def tearDown(self):
        """Clean up sys.path to avoid side effects."""
        sys.path.remove(self.skills_path)
        # Remove the module from cache to ensure it's re-imported cleanly if needed
        if "feed_feedback" in sys.modules:
            del sys.modules["feed_feedback"]

    def test_extract_session_id_numeric(self):
        # Case 1: Numeric Session ID (as seen in exploration)
        branch = "plan-jules-feedback-loop-11292279998332410515"
        self.assertEqual(self.feed_feedback.extract_session_id(branch), "11292279998332410515")

    def test_extract_session_id_uuid(self):
        # Case 2: UUID Session ID
        branch = "feature-update-123e4567-e89b-12d3-a456-426614174000"
        self.assertEqual(
            self.feed_feedback.extract_session_id(branch),
            "123e4567-e89b-12d3-a456-426614174000",
        )

    def test_extract_session_id_short_fallback(self):
        # Case 3: Short suffix (should return None if < 10 chars to avoid false positives)
        branch = "feature-update-v1"
        self.assertIsNone(self.feed_feedback.extract_session_id(branch))

    def test_extract_session_id_from_body(self):
        # Case 4: Link in body
        body = "Check out the session: https://jules.google.com/session/11292279998332410515 for details."
        self.assertEqual(self.feed_feedback.extract_session_id_from_body(body), "11292279998332410515")

        # UUID in body
        body_uuid = "Session: https://jules.google.com/session/123e4567-e89b-12d3-a456-426614174000"
        self.assertEqual(
            self.feed_feedback.extract_session_id_from_body(body_uuid),
            "123e4567-e89b-12d3-a456-426614174000",
        )

        # No link
        self.assertIsNone(self.feed_feedback.extract_session_id_from_body("Just a normal description."))

    def test_should_trigger_feedback_ci_failed(self):
        pr = {"statusCheckRollup": {"state": "FAILURE"}, "latestReviews": []}
        self.assertTrue(self.feed_feedback.should_trigger_feedback(pr))

    def test_should_trigger_feedback_changes_requested(self):
        pr = {
            "statusCheckRollup": {"state": "SUCCESS"},
            "latestReviews": [{"state": "CHANGES_REQUESTED"}],
        }
        self.assertTrue(self.feed_feedback.should_trigger_feedback(pr))

    def test_should_trigger_feedback_negative(self):
        pr = {
            "statusCheckRollup": {"state": "SUCCESS"},
            "latestReviews": [{"state": "APPROVED"}],
        }
        self.assertFalse(self.feed_feedback.should_trigger_feedback(pr))

        pr_pending = {"statusCheckRollup": {"state": "PENDING"}, "latestReviews": []}
        self.assertFalse(self.feed_feedback.should_trigger_feedback(pr_pending))

    def test_extract_session_id_complex_branch(self):
        # Real world example with hyphens in name
        branch = "scribe-protocol-drift-fix-5103170759952896668"
        self.assertEqual(self.feed_feedback.extract_session_id(branch), "5103170759952896668")

    def test_should_skip_feedback(self):
        # Case 1: Feedback is fresh (comment > commit)
        pr_data = {"commits": [{"committedDate": "2023-01-01T10:00:00Z"}]}
        comments_data = {
            "comments": [
                {
                    "body": "# Task: Fix Pull Request\nDetails...",
                    "createdAt": "2023-01-01T10:05:00Z",
                }
            ]
        }
        self.assertTrue(self.feed_feedback.should_skip_feedback(pr_data, comments_data))

        # Case 2: Feedback is stale (comment < commit)
        pr_data["commits"][0]["committedDate"] = "2023-01-01T10:10:00Z"
        self.assertFalse(self.feed_feedback.should_skip_feedback(pr_data, comments_data))

        # Case 3: Last comment is not feedback
        comments_data["comments"][0]["body"] = "Just a regular comment"
        comments_data["comments"][0]["createdAt"] = "2023-01-01T10:20:00Z"  # Even if newer
        self.assertFalse(self.feed_feedback.should_skip_feedback(pr_data, comments_data))

        # Case 4: Feedback with marker in HTML comment
        comments_data["comments"][0]["body"] = "Feedback sent. \n<!-- # Task: Fix Pull Request -->"
        comments_data["comments"][0]["createdAt"] = "2023-01-01T12:00:00Z"
        # Commit is old
        pr_data["commits"][0]["committedDate"] = "2023-01-01T10:10:00Z"
        self.assertTrue(self.feed_feedback.should_skip_feedback(pr_data, comments_data))


if __name__ == "__main__":
    unittest.main()
