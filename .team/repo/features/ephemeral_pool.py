"""Ephemeral session pool for reusable repoless sessions.

Uses the Jules API January 2026 repoless sessions feature to create
ephemeral cloud dev environments that can be reused across multiple
tasks, reducing session count and avoiding daily limits (100/day).
"""

from typing import Any

from repo.core.client import TeamClient

# Title prefixes for different ephemeral session types
REVIEWER_TITLE_PREFIX = "🔍 [Ephemeral] PR Reviewer"
RESEARCH_TITLE_PREFIX = "📚 [Ephemeral] Research"
SUPPORT_TITLE_PREFIX = "💡 [Ephemeral] Support"

# States that indicate a session can be reused
REUSABLE_STATES = {"IN_PROGRESS", "AWAITING_USER_FEEDBACK", "PAUSED"}

# States that indicate a session is finished
FINISHED_STATES = {"COMPLETED", "FAILED"}


class EphemeralSessionPool:
    """Pool of reusable ephemeral (repoless) Jules sessions.

    This class manages a pool of repoless sessions that can be reused
    across multiple tasks to avoid hitting the 100 sessions/day limit.

    Ephemeral sessions are identified by title prefixes and can be
    reused as long as they're not in COMPLETED or FAILED states.

    Example usage:
        pool = EphemeralSessionPool(client)

        # Get or create a PR reviewer session
        session_id = pool.get_or_create_reviewer()

        # Send a review request
        client.send_message(session_id, "Review this PR: https://github.com/...")

    """

    def __init__(self, client: TeamClient):
        """Initialize the pool with a Jules API client.

        Args:
            client: TeamClient instance for Jules API calls.

        """
        self.client = client
        # Cache of known session IDs by type
        self._session_cache: dict[str, str] = {}

    def _find_reusable_session(self, title_prefix: str) -> str | None:
        """Find an existing reusable session by title prefix.

        Args:
            title_prefix: The title prefix to search for.

        Returns:
            Session ID if found and reusable, None otherwise.

        """
        try:
            sessions = self.client.list_sessions().get("sessions", [])
        except Exception as e:
            print(f"  Failed to list sessions: {e}")
            return None

        for session in sessions:
            title = session.get("title") or ""
            state = (session.get("state") or "").upper()
            session_id = session.get("name", "").split("/")[-1]

            if title_prefix.lower() in title.lower():
                if state in REUSABLE_STATES:
                    print(f"  Found reusable session: {session_id} (state: {state})")
                    return session_id
                if state in FINISHED_STATES:
                    # Session is finished, skip it
                    continue

        return None

    def get_or_create_reviewer(self) -> str | None:
        """Get or create an ephemeral PR reviewer session.

        The reviewer session can review PRs by URL without needing
        repository context. It can be reused for multiple PR reviews.

        Returns:
            Session ID, or None on failure.

        """
        # Check cache first
        if cached := self._session_cache.get("reviewer"):
            # Verify it's still reusable
            try:
                session = self.client.get_session(cached)
                state = (session.get("state") or "").upper()
                if state in REUSABLE_STATES:
                    return cached
            except Exception:
                pass  # Cache invalid, find or create new

        # Try to find existing reviewer session
        if session_id := self._find_reusable_session(REVIEWER_TITLE_PREFIX):
            self._session_cache["reviewer"] = session_id
            return session_id

        # Create new reviewer session
        print("  Creating new ephemeral PR reviewer session...")
        prompt = """# 🔍 Ephemeral PR Code Reviewer

You are a code review specialist. Your role is to review Pull Requests
when given a GitHub PR URL.

## Your Capabilities
- Fetch and analyze PR diffs via the provided URL
- Identify code quality issues, bugs, and security concerns
- Suggest improvements and best practices
- Recommend approvals, changes, or reverts

## Review Process
1. When given a PR URL, fetch and analyze the changes
2. Provide structured feedback:
   - **Summary**: Brief overview of changes
   - **Issues Found**: List any problems (bugs, security, style)
   - **Suggestions**: Improvement recommendations
   - **Verdict**: APPROVE / REQUEST_CHANGES / REVERT_RECOMMENDED
3. If recommending revert, provide specific fix instructions

## Important Notes
- You are a reviewer, not a coder in this session
- Provide actionable feedback that can be used to create fix sessions
- Be thorough but concise
- Reference specific line numbers when possible

## Session Reuse
This session is designed for reuse. Each new message may contain a
different PR URL to review. Treat each as an independent review task.
"""

        try:
            result = self.client.create_repoless_session(
                prompt=prompt,
                title=REVIEWER_TITLE_PREFIX,
                require_plan_approval=False,
            )
            session_id = result.get("name", "").split("/")[-1]
            print(f"  Created ephemeral reviewer session: {session_id}")
            self._session_cache["reviewer"] = session_id
            return session_id
        except Exception as e:
            print(f"  Failed to create reviewer session: {e}")
            return None

    def get_or_create_research(self) -> str | None:
        """Get or create an ephemeral research session.

        The research session can perform technical research, analyze
        patterns, and provide recommendations without repo context.

        Returns:
            Session ID, or None on failure.

        """
        # Check cache first
        if cached := self._session_cache.get("research"):
            try:
                session = self.client.get_session(cached)
                state = (session.get("state") or "").upper()
                if state in REUSABLE_STATES:
                    return cached
            except Exception:
                pass

        # Try to find existing research session
        if session_id := self._find_reusable_session(RESEARCH_TITLE_PREFIX):
            self._session_cache["research"] = session_id
            return session_id

        # Create new research session
        print("  Creating new ephemeral research session...")
        prompt = """# 📚 Ephemeral Research Assistant

You are a technical research specialist. Your role is to research
topics, analyze patterns, and provide recommendations.

## Your Capabilities
- Research technical topics and best practices
- Analyze architectural patterns
- Compare technologies and approaches
- Provide implementation recommendations

## How to Use
Send me a research question or topic, and I'll provide a comprehensive
analysis with actionable recommendations.

## Session Reuse
This session is designed for reuse. Each message may contain a
different research topic. Treat each as an independent research task.
"""

        try:
            result = self.client.create_repoless_session(
                prompt=prompt,
                title=RESEARCH_TITLE_PREFIX,
                require_plan_approval=False,
            )
            session_id = result.get("name", "").split("/")[-1]
            print(f"  Created ephemeral research session: {session_id}")
            self._session_cache["research"] = session_id
            return session_id
        except Exception as e:
            print(f"  Failed to create research session: {e}")
            return None

    def get_or_create_support(self) -> str | None:
        """Get or create an ephemeral support session.

        The support session provides technical guidance and answers
        questions without repository context.

        Returns:
            Session ID, or None on failure.

        """
        # Check cache first
        if cached := self._session_cache.get("support"):
            try:
                session = self.client.get_session(cached)
                state = (session.get("state") or "").upper()
                if state in REUSABLE_STATES:
                    return cached
            except Exception:
                pass

        # Try to find existing support session
        if session_id := self._find_reusable_session(SUPPORT_TITLE_PREFIX):
            self._session_cache["support"] = session_id
            return session_id

        # Create new support session
        print("  Creating new ephemeral support session...")
        prompt = """# 💡 Ephemeral Technical Support

You are a technical support specialist. Your role is to answer
questions, provide guidance, and help with technical issues.

## Your Capabilities
- Answer technical questions
- Provide architectural guidance
- Explain concepts and patterns
- Suggest solutions to problems

## How to Use
Send me a question or describe your problem, and I'll provide
clear, actionable guidance.

## Session Reuse
This session is designed for reuse. Each message may contain a
different question. Treat each as an independent support request.
"""

        try:
            result = self.client.create_repoless_session(
                prompt=prompt,
                title=SUPPORT_TITLE_PREFIX,
                require_plan_approval=False,
            )
            session_id = result.get("name", "").split("/")[-1]
            print(f"  Created ephemeral support session: {session_id}")
            self._session_cache["support"] = session_id
            return session_id
        except Exception as e:
            print(f"  Failed to create support session: {e}")
            return None

    def get_pool_stats(self) -> dict[str, Any]:
        """Get statistics about the ephemeral session pool.

        Returns:
            Dict with pool statistics.

        """
        stats = {
            "cached_sessions": len(self._session_cache),
            "sessions": {},
        }

        for session_type, session_id in self._session_cache.items():
            try:
                session = self.client.get_session(session_id)
                stats["sessions"][session_type] = {
                    "id": session_id,
                    "state": session.get("state"),
                    "title": session.get("title"),
                }
            except Exception:
                stats["sessions"][session_type] = {
                    "id": session_id,
                    "state": "UNKNOWN",
                    "error": "Failed to fetch session",
                }

        return stats
