"""Unit tests for the ephemeral session pool and PR reviewer."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add .team to path so we can import repo.features
REPO_ROOT = Path(__file__).parents[3]
TEAM_PATH = REPO_ROOT / ".team"
if str(TEAM_PATH) not in sys.path:
    sys.path.append(str(TEAM_PATH))

from repo.features.ephemeral_pool import (  # noqa: E402
    PERSONA_TITLE_PREFIX,
    REVIEWER_TITLE_PREFIX,
    REUSABLE_STATES,
    EphemeralSessionPool,
)
from repo.features.maya_analyst import (  # noqa: E402
    AnalysisRequest,
    PersonaAnalyst,
    PersonaInsight,
    parse_persona_insight,
)
from repo.features.pr_reviewer import (  # noqa: E402
    PRReviewer,
    parse_review_response,
)


class TestEphemeralSessionPool:
    """Tests for EphemeralSessionPool."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock TeamClient."""
        client = MagicMock()
        client.list_sessions.return_value = {"sessions": []}
        client.get_session.return_value = {"state": "IN_PROGRESS"}
        client.create_repoless_session.return_value = {"name": "sessions/new-123"}
        return client

    @pytest.fixture
    def pool(self, mock_client):
        """Create an EphemeralSessionPool with mock client."""
        return EphemeralSessionPool(mock_client)

    def test_creates_new_reviewer_when_none_exists(self, pool, mock_client):
        """Creates new reviewer session when no reusable one exists."""
        session_id = pool.get_or_create_reviewer()

        assert session_id == "new-123"
        mock_client.create_repoless_session.assert_called_once()
        call_kwargs = mock_client.create_repoless_session.call_args[1]
        assert REVIEWER_TITLE_PREFIX in call_kwargs["title"]

    def test_reuses_existing_reviewer_session(self, pool, mock_client):
        """Reuses existing reviewer session in reusable state."""
        mock_client.list_sessions.return_value = {
            "sessions": [
                {
                    "name": "sessions/existing-456",
                    "title": f"{REVIEWER_TITLE_PREFIX} test",
                    "state": "IN_PROGRESS",
                }
            ]
        }

        session_id = pool.get_or_create_reviewer()

        assert session_id == "existing-456"
        mock_client.create_repoless_session.assert_not_called()

    def test_skips_completed_sessions(self, pool, mock_client):
        """Skips completed sessions and creates new one."""
        mock_client.list_sessions.return_value = {
            "sessions": [
                {
                    "name": "sessions/old-completed",
                    "title": f"{REVIEWER_TITLE_PREFIX} old",
                    "state": "COMPLETED",
                }
            ]
        }

        session_id = pool.get_or_create_reviewer()

        assert session_id == "new-123"
        mock_client.create_repoless_session.assert_called_once()

    def test_skips_failed_sessions(self, pool, mock_client):
        """Skips failed sessions and creates new one."""
        mock_client.list_sessions.return_value = {
            "sessions": [
                {
                    "name": "sessions/old-failed",
                    "title": f"{REVIEWER_TITLE_PREFIX} failed",
                    "state": "FAILED",
                }
            ]
        }

        session_id = pool.get_or_create_reviewer()

        assert session_id == "new-123"

    def test_cache_used_on_subsequent_calls(self, pool, mock_client):
        """Cache is used for subsequent calls."""
        mock_client.list_sessions.return_value = {
            "sessions": [
                {
                    "name": "sessions/cached-789",
                    "title": f"{REVIEWER_TITLE_PREFIX}",
                    "state": "IN_PROGRESS",
                }
            ]
        }

        # First call
        session_id1 = pool.get_or_create_reviewer()
        # Second call
        session_id2 = pool.get_or_create_reviewer()

        assert session_id1 == session_id2 == "cached-789"
        # get_session called to verify cache on second call
        assert mock_client.get_session.call_count >= 1

    def test_all_reusable_states_are_accepted(self, pool, mock_client):
        """All defined reusable states allow session reuse."""
        for state in REUSABLE_STATES:
            mock_client.list_sessions.return_value = {
                "sessions": [
                    {
                        "name": f"sessions/state-{state}",
                        "title": f"{REVIEWER_TITLE_PREFIX}",
                        "state": state,
                    }
                ]
            }
            pool._session_cache.clear()  # Clear cache between tests

            session_id = pool.get_or_create_reviewer()

            assert session_id == f"state-{state}"


class TestPRReviewer:
    """Tests for PRReviewer."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock TeamClient."""
        client = MagicMock()
        client.list_sessions.return_value = {"sessions": []}
        client.get_session.return_value = {"state": "IN_PROGRESS"}
        client.create_repoless_session.return_value = {"name": "sessions/reviewer-123"}
        client.send_message.return_value = {}
        return client

    @pytest.fixture
    def reviewer(self, mock_client):
        """Create a PRReviewer with mock client."""
        return PRReviewer(mock_client)

    def test_request_review_sends_message(self, reviewer, mock_client):
        """Request review sends message to reviewer session."""
        pr_url = "https://github.com/owner/repo/pull/42"

        result = reviewer.request_review(pr_url)

        assert result.request_sent is True
        assert result.session_id == "reviewer-123"
        assert result.pr_url == pr_url
        mock_client.send_message.assert_called_once()
        message = mock_client.send_message.call_args[0][1]
        assert pr_url in message

    def test_request_review_with_context(self, reviewer, mock_client):
        """Request review includes context in message."""
        pr_url = "https://github.com/owner/repo/pull/42"
        context = "Focus on security changes"

        reviewer.request_review(pr_url, context=context)

        message = mock_client.send_message.call_args[0][1]
        assert context in message

    def test_post_merge_review_has_different_message(self, reviewer, mock_client):
        """Post-merge reviews have different message format."""
        pr_url = "https://github.com/owner/repo/pull/42"

        reviewer.request_review(pr_url, post_merge=True)

        message = mock_client.send_message.call_args[0][1]
        assert "Post-Merge" in message
        assert "REVERT_RECOMMENDED" in message

    def test_batch_review_sends_multiple_messages(self, reviewer, mock_client):
        """Batch review sends message for each PR."""
        pr_urls = [
            "https://github.com/owner/repo/pull/1",
            "https://github.com/owner/repo/pull/2",
            "https://github.com/owner/repo/pull/3",
        ]

        results = reviewer.request_batch_review(pr_urls)

        assert len(results) == 3
        assert all(r.request_sent for r in results)
        assert mock_client.send_message.call_count == 3

    def test_handles_session_creation_failure(self, reviewer, mock_client):
        """Handles failure to create reviewer session."""
        mock_client.create_repoless_session.side_effect = Exception("API Error")

        result = reviewer.request_review("https://github.com/owner/repo/pull/42")

        assert result.request_sent is False
        assert "Failed" in result.error


class TestParseReviewResponse:
    """Tests for parse_review_response."""

    def test_parses_approve_verdict(self):
        """Parses APPROVE verdict correctly."""
        response = """
## Summary
This PR adds a new feature.

## Issues Found
- None

## Verdict
APPROVE
"""
        result = parse_review_response(response)

        assert result.verdict == "APPROVE"

    def test_parses_request_changes_verdict(self):
        """Parses REQUEST_CHANGES verdict correctly."""
        response = """
## Summary
This PR has issues.

## Issues Found
- Missing tests
- Security concern

## Verdict: REQUEST_CHANGES
"""
        result = parse_review_response(response)

        assert result.verdict == "REQUEST_CHANGES"
        assert len(result.issues) >= 1

    def test_parses_revert_recommended_verdict(self):
        """Parses REVERT_RECOMMENDED verdict correctly."""
        response = """
## Summary
Critical bug introduced.

## Issues Found
- Breaks production

## Verdict: REVERT_RECOMMENDED

## Fix Instructions
Revert commit abc123 and add tests.
"""
        result = parse_review_response(response)

        assert result.verdict == "REVERT_RECOMMENDED"
        assert result.fix_instructions is not None
        assert "Revert" in result.fix_instructions

    def test_extracts_issues_list(self):
        """Extracts issues list from response."""
        response = """
## Issues Found
- First issue
- Second issue
- Third issue
"""
        result = parse_review_response(response)

        assert len(result.issues) == 3
        assert "First issue" in result.issues

    def test_extracts_suggestions_list(self):
        """Extracts suggestions list from response."""
        response = """
## Suggestions
- Add more tests
- Improve documentation
"""
        result = parse_review_response(response)

        assert len(result.suggestions) == 2
        assert "Add more tests" in result.suggestions


class TestCreateRepolessSession:
    """Tests for TeamClient.create_repoless_session."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock for testing create_repoless_session."""
        from unittest.mock import patch

        with patch("repo.core.client._request_with_retry") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"name": "sessions/repoless-123"}
            mock_request.return_value = mock_response

            from repo.core.client import TeamClient

            client = TeamClient(api_key="test-key")
            yield client, mock_request

    def test_creates_session_without_source_context(self, mock_client):
        """Creates session without sourceContext for repoless."""
        client, mock_request = mock_client

        client.create_repoless_session(
            prompt="Test prompt",
            title="Test Title",
        )

        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        data = call_kwargs["json"]

        # No sourceContext for repoless sessions
        assert "sourceContext" not in data
        assert data["automationMode"] == "MANUAL"
        assert data["prompt"] == "Test prompt"

    def test_sets_manual_automation_mode(self, mock_client):
        """Repoless sessions use MANUAL automation mode."""
        client, mock_request = mock_client

        client.create_repoless_session(prompt="Test")

        data = mock_request.call_args[1]["json"]
        assert data["automationMode"] == "MANUAL"


class TestPersonaSessionPool:
    """Tests for generic persona sessions in EphemeralSessionPool."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock TeamClient."""
        client = MagicMock()
        client.list_sessions.return_value = {"sessions": []}
        client.get_session.return_value = {"state": "IN_PROGRESS"}
        client.create_repoless_session.return_value = {"name": "sessions/persona-123"}
        return client

    @pytest.fixture
    def pool(self, mock_client):
        """Create an EphemeralSessionPool with mock client."""
        return EphemeralSessionPool(mock_client)

    def test_reuses_existing_persona_session(self, pool, mock_client):
        """Reuses existing persona session in reusable state."""
        mock_client.list_sessions.return_value = {
            "sessions": [
                {
                    "name": "sessions/existing-maya",
                    "title": f"💝 {PERSONA_TITLE_PREFIX} maya",
                    "state": "IN_PROGRESS",
                }
            ]
        }

        session_id = pool.get_or_create_persona_session("maya")

        assert session_id == "existing-maya"
        mock_client.create_repoless_session.assert_not_called()


class TestPersonaAnalyst:
    """Tests for PersonaAnalyst."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock TeamClient."""
        client = MagicMock()
        client.list_sessions.return_value = {"sessions": []}
        client.get_session.return_value = {"state": "IN_PROGRESS"}
        client.create_repoless_session.return_value = {"name": "sessions/persona-456"}
        client.send_message.return_value = {}
        return client

    @pytest.fixture
    def mock_pool(self, mock_client):
        """Create a mock EphemeralSessionPool."""
        pool = MagicMock()
        pool.get_or_create_persona_session.return_value = "persona-456"
        return pool

    @pytest.fixture
    def analyst(self, mock_client, mock_pool):
        """Create a PersonaAnalyst with mock client and pool."""
        repo_info = {"owner": "test-owner", "repo": "test-repo"}
        return PersonaAnalyst(mock_client, repo_info, persona_id="maya", pool=mock_pool)

    def test_request_analysis_sends_message(self, analyst, mock_client, mock_pool):
        """Request analysis sends message to persona session."""
        request = AnalysisRequest(
            content="Button is hard to find",
            source="support ticket"
        )

        result = analyst.request_analysis(request)

        assert result.request_sent is True
        assert result.session_id == "persona-456"
        assert result.persona_id == "maya"
        mock_client.send_message.assert_called_once()
        message = mock_client.send_message.call_args[0][1]
        assert "Button is hard to find" in message
        assert "support ticket" in message

    def test_request_analysis_includes_context(self, analyst, mock_client, mock_pool):
        """Request analysis includes context in message."""
        request = AnalysisRequest(
            content="Page loads slowly",
            context="User on mobile network"
        )

        analyst.request_analysis(request)

        message = mock_client.send_message.call_args[0][1]
        assert "User on mobile network" in message


class TestParsePersonaInsight:
    """Tests for parse_persona_insight."""

    def test_parses_complete_insight(self):
        """Parses complete insight with all fields."""
        response = """
```markdown
---
type: insight
title: Improve button visibility
severity: high
labels: [ux, usability]
---

## Description
The submit button is hard to find on the checkout page.

## User Impact
Users abandon checkout because they can't find the button.

## Recommendation
Make the button larger and use a contrasting color.

## Evidence
5 support tickets this week about missing submit button.
```
"""
        insight = parse_persona_insight(response)

        assert insight is not None
        assert insight.title == "Improve button visibility"
        assert insight.severity == "high"
        assert "ux" in insight.labels
        assert "usability" in insight.labels
        assert "hard to find" in insight.description
        assert "abandon checkout" in insight.user_impact
        assert "contrasting color" in insight.recommendation
        assert "5 support tickets" in insight.evidence

    def test_parses_insight_without_code_block(self):
        """Parses insight without code block wrapper."""
        response = """
---
type: insight
title: Add loading indicator
severity: medium
labels: [ux, performance]
---

## Description
No feedback when page is loading.

## User Impact
Users think the app is frozen.

## Recommendation
Add a spinner or progress bar.

## Evidence
User interviews mentioned confusion during waits.
"""
        insight = parse_persona_insight(response)

        assert insight is not None
        assert insight.title == "Add loading indicator"
        assert insight.severity == "medium"

    def test_returns_none_for_invalid_format(self):
        """Returns None when format is invalid."""
        response = "This is not a valid insight format."
        insight = parse_persona_insight(response)
        assert insight is None

    def test_insight_to_issue_body(self):
        """Tests PersonaInsight.to_issue_body() formatting."""
        insight = PersonaInsight(
            title="Test Issue",
            severity="high",
            labels=["ux"],
            description="Test description",
            user_impact="Users are affected",
            recommendation="Fix it",
            evidence="User reports",
        )

        body = insight.to_issue_body(persona_id="maya")

        assert "🟠 Severity: HIGH" in body
        assert "Test description" in body
        assert "Users are affected" in body
        assert "Fix it" in body
        assert "maya" in body
