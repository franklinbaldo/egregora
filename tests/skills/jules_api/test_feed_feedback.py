import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add skills directory to path to allow importing the script module
skills_path = Path(__file__).parent.parent.parent.parent / ".claude" / "skills" / "jules-api"
sys.path.append(str(skills_path))

import feed_feedback

class TestFeedFeedback(unittest.TestCase):

    def test_extract_session_id_numeric(self):
        # Case 1: Numeric Session ID (as seen in exploration)
        branch = "plan-jules-feedback-loop-11292279998332410515"
        self.assertEqual(feed_feedback.extract_session_id(branch), "11292279998332410515")

    def test_extract_session_id_uuid(self):
        # Case 2: UUID Session ID
        branch = "feature-update-123e4567-e89b-12d3-a456-426614174000"
        self.assertEqual(feed_feedback.extract_session_id(branch), "123e4567-e89b-12d3-a456-426614174000")

    def test_extract_session_id_short_fallback(self):
        # Case 3: Short suffix (should return None if < 10 chars to avoid false positives)
        branch = "feature-update-v1"
        self.assertIsNone(feed_feedback.extract_session_id(branch))

    def test_extract_session_id_from_body(self):
        # Case 4: Link in body
        body = "Check out the session: https://jules.google/sessions/11292279998332410515 for details."
        self.assertEqual(feed_feedback.extract_session_id_from_body(body), "11292279998332410515")

        # UUID in body
        body_uuid = "Session: https://jules.google/sessions/123e4567-e89b-12d3-a456-426614174000"
        self.assertEqual(feed_feedback.extract_session_id_from_body(body_uuid), "123e4567-e89b-12d3-a456-426614174000")

        # No link
        self.assertIsNone(feed_feedback.extract_session_id_from_body("Just a normal description."))

    def test_should_trigger_feedback_ci_failed(self):
        pr = {
            "statusCheckRollup": {"state": "FAILURE"},
            "latestReviews": []
        }
        self.assertTrue(feed_feedback.should_trigger_feedback(pr))

    def test_should_trigger_feedback_changes_requested(self):
        pr = {
            "statusCheckRollup": {"state": "SUCCESS"},
            "latestReviews": [{"state": "CHANGES_REQUESTED"}]
        }
        self.assertTrue(feed_feedback.should_trigger_feedback(pr))

    def test_should_trigger_feedback_negative(self):
        pr = {
            "statusCheckRollup": {"state": "SUCCESS"},
            "latestReviews": [{"state": "APPROVED"}]
        }
        self.assertFalse(feed_feedback.should_trigger_feedback(pr))

        pr_pending = {
             "statusCheckRollup": {"state": "PENDING"},
             "latestReviews": []
        }
        self.assertFalse(feed_feedback.should_trigger_feedback(pr_pending))

    def test_extract_session_id_complex_branch(self):
        # Real world example with hyphens in name
        branch = "scribe-protocol-drift-fix-5103170759952896668"
        self.assertEqual(feed_feedback.extract_session_id(branch), "5103170759952896668")

    def test_should_skip_feedback(self):
        # Case 1: Feedback is fresh (comment > commit)
        pr_data = {
            "commits": [{"committedDate": "2023-01-01T10:00:00Z"}]
        }
        comments_data = {
            "comments": [
                {"body": "# Task: Fix Pull Request\nDetails...", "createdAt": "2023-01-01T10:05:00Z"}
            ]
        }
        self.assertTrue(feed_feedback.should_skip_feedback(pr_data, comments_data))

        # Case 2: Feedback is stale (comment < commit)
        pr_data["commits"][0]["committedDate"] = "2023-01-01T10:10:00Z"
        self.assertFalse(feed_feedback.should_skip_feedback(pr_data, comments_data))

        # Case 3: Last comment is not feedback
        comments_data["comments"][0]["body"] = "Just a regular comment"
        comments_data["comments"][0]["createdAt"] = "2023-01-01T10:20:00Z" # Even if newer
        self.assertFalse(feed_feedback.should_skip_feedback(pr_data, comments_data))

        # Case 4: Feedback with marker in HTML comment
        comments_data["comments"][0]["body"] = "Feedback sent. \n<!-- # Task: Fix Pull Request -->"
        comments_data["comments"][0]["createdAt"] = "2023-01-01T12:00:00Z"
        # Commit is old
        pr_data["commits"][0]["committedDate"] = "2023-01-01T10:10:00Z"
        self.assertTrue(feed_feedback.should_skip_feedback(pr_data, comments_data))

if __name__ == '__main__':
    unittest.main()
