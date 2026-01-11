"""Manager classes for Jules scheduler operations."""

import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from jules.client import JulesClient
from jules.exceptions import BranchError, MergeError
from jules.github import (
    _extract_session_id,
    get_pr_by_session_id_any_state,
    get_pr_details_via_gh,
)
from jules.reconciliation_tracker import ReconciliationTracker
from jules.scheduler import sprint_manager, JULES_BRANCH, JULES_SCHEDULER_PREFIX
from jules.scheduler_models import CycleState, PersonaConfig, PRStatus, SessionRequest

# Timeout threshold for stuck sessions (in hours)
SESSION_TIMEOUT_HOURS = 0.5  # 30 minutes


class BranchManager:
    """Handles all git branch operations for the scheduler."""

    def __init__(self, jules_branch: str = JULES_BRANCH):
        """Initialize branch manager.

        Args:
            jules_branch: Name of the main Jules integration branch
        """
        self.jules_branch = jules_branch

    def ensure_jules_branch_exists(self) -> None:
        """Ensure the Jules branch exists and is healthy.

        Creates the branch from main if it doesn't exist, or updates it
        from main if it exists and isn't drifted.

        Raises:
            BranchError: If branch operations fail
        """
        try:
            subprocess.run(["git", "fetch", "origin"], check=True, capture_output=True)

            # Check if branch exists
            result = subprocess.run(
                ["git", "ls-remote", "--heads", "origin", self.jules_branch],
                capture_output=True,
                text=True,
                check=True,
            )

            if result.stdout.strip():
                # Branch exists - check if drifted
                if self._is_drifted():
                    self._rotate_drifted_branch()
                else:
                    print(f"Branch '{self.jules_branch}' exists and is healthy. Updating from main...")
                    if self._update_from_main():
                        return

            # Create fresh branch from main
            print(f"Branch '{self.jules_branch}' needs recreation. Creating from main...")
            result = subprocess.run(
                ["git", "rev-parse", "origin/main"], capture_output=True, text=True, check=True
            )
            main_sha = result.stdout.strip()
            subprocess.run(
                ["git", "push", "--force", "origin", f"{main_sha}:refs/heads/{self.jules_branch}"],
                check=True,
                capture_output=True,
            )
            print(f"Created fresh '{self.jules_branch}' branch from main at {main_sha[:12]}")

        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            raise BranchError(f"Failed to ensure jules branch exists: {stderr}") from e

    def create_session_branch(
        self,
        base_branch: str,
        persona_id: str,
        base_pr_number: str = "",
        last_session_id: str | None = None,
    ) -> str:
        """Create a short, stable base branch for a Jules session.

        Args:
            base_branch: Source branch to branch from
            persona_id: Persona identifier
            base_pr_number: Previous PR number (for naming)
            last_session_id: Previous session ID (unused but kept for compatibility)

        Returns:
            Name of the created branch

        Note:
            Falls back to base_branch if creation fails.
        """
        if base_pr_number:
            branch_name = f"{JULES_SCHEDULER_PREFIX}-{persona_id}-pr{base_pr_number}"
        else:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
            branch_name = f"{JULES_SCHEDULER_PREFIX}-{persona_id}-main-{timestamp}"

        try:
            # Fetch base branch
            subprocess.run(
                ["git", "fetch", "origin", base_branch], check=True, capture_output=True
            )

            # Get SHA
            result = subprocess.run(
                ["git", "rev-parse", f"origin/{base_branch}"],
                capture_output=True,
                text=True,
                check=True,
            )
            base_sha = result.stdout.strip()
            print(f"Base branch '{base_branch}' is at SHA: {base_sha[:12]}")

            # Push new branch
            subprocess.run(
                ["git", "push", "origin", f"{base_sha}:refs/heads/{branch_name}"],
                check=True,
                capture_output=True,
            )
            print(f"Prepared base branch '{branch_name}' from {base_branch}")
            return branch_name

        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            print(f"Failed to prepare base branch: {stderr}", file=sys.stderr)
            print(f"Falling back to base branch: {base_branch}")
            return base_branch

    def _is_drifted(self) -> bool:
        """Check if Jules branch has conflicts with main.

        Returns:
            True if there are conflicts, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "merge-tree", "--write-tree", f"origin/{self.jules_branch}", "origin/main"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 1:
                print(
                    f"Drift detected: Conflicting changes between 'origin/{self.jules_branch}' and 'origin/main'."
                )
                return True
            if result.returncode > 1:
                stderr = result.stderr.strip()
                print(
                    f"Warning: git merge-tree failed with code {result.returncode}: {stderr}. "
                    f"Assuming NO drift to avoid accidental rotation."
                )
                return False
            return False
        except Exception as e:
            print(f"Warning: Error checking drift: {e}. Assuming NO drift.")
            return False

    def _rotate_drifted_branch(self) -> tuple[int, int] | None:
        """Rename drifted Jules branch with sprint number and create PR.

        Returns:
            Tuple of (pr_number, sprint_number) if successful, None if failed
        """
        current_sprint = sprint_manager.get_current_sprint()
        drift_branch = f"{self.jules_branch}-sprint-{current_sprint}"

        print(f"Drift detected in '{self.jules_branch}'. Rotating to '{drift_branch}'...")

        try:
            # Copy branch
            subprocess.run(
                ["git", "push", "origin", f"origin/{self.jules_branch}:refs/heads/{drift_branch}"],
                check=True,
                capture_output=True,
            )

            # Create PR
            pr_title = f"Sprint {current_sprint} - Drifted work from {self.jules_branch}"
            pr_body = (
                f"This PR contains work from Sprint {current_sprint}.\n\n"
                f"**Sprint:** {current_sprint}\n"
                f"**Branch:** {drift_branch}\n\n"
                f"The `{self.jules_branch}` branch became unmergeable with `main`. "
                f"A reconciliation session will be created to merge these changes back."
            )

            try:
                result = subprocess.run(
                    [
                        "gh",
                        "pr",
                        "create",
                        "--head",
                        drift_branch,
                        "--base",
                        "main",
                        "--title",
                        pr_title,
                        "--body",
                        pr_body,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                # Extract PR number from output (URL format: https://github.com/owner/repo/pull/123)
                pr_url = result.stdout.strip()
                pr_number = int(pr_url.split("/")[-1])
                print(f"Created PR #{pr_number} for sprint {current_sprint}: {drift_branch}")
                return (pr_number, current_sprint)

            except subprocess.CalledProcessError as e:
                stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
                print(f"Warning: Failed to create PR for drift branch: {stderr}", file=sys.stderr)
                return None

        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            print(f"Warning: Failed to rotate jules branch fully: {stderr}", file=sys.stderr)
            return None

    def _update_from_main(self) -> bool:
        """Update Jules branch from main.

        Returns:
            True if successful, False if conflicts (triggers rotation)
        """
        try:
            subprocess.run(["git", "config", "user.name", "Jules Bot"], check=False)
            subprocess.run(["git", "config", "user.email", "jules-bot@google.com"], check=False)
            subprocess.run(
                ["git", "checkout", "-B", self.jules_branch, f"origin/{self.jules_branch}"],
                check=True,
                capture_output=True,
            )
            print(f"Merging origin/main into '{self.jules_branch}'...")
            subprocess.run(
                ["git", "merge", "origin/main", "--no-edit"], check=True, capture_output=True
            )
            subprocess.run(["git", "push", "origin", self.jules_branch], check=True, capture_output=True)
            print(f"Successfully updated '{self.jules_branch}' from main.")
            return True
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            print(f"Failed to update jules from main: {stderr}. Treating as drift...")
            self._rotate_drifted_branch()
            return False

    def sync_with_main(self) -> tuple[int, int] | None:
        """Sync Jules branch with main after a PR merge.

        This ensures the next session is based on the latest main,
        capturing both cycle PRs and external changes to main.

        If sync fails (usually due to conflicts), treats it as drift:
        creates a backup branch (jules-sprint-N) with a PR for manual
        reconciliation, then recreates jules from main.

        Returns:
            Tuple of (pr_number, sprint_number) if drift occurred, None otherwise
        """
        try:
            subprocess.run(["git", "fetch", "origin"], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Jules Bot"], check=False)
            subprocess.run(["git", "config", "user.email", "jules-bot@google.com"], check=False)
            subprocess.run(
                ["git", "checkout", "-B", self.jules_branch, f"origin/{self.jules_branch}"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "merge", "origin/main", "--no-edit"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "push", "origin", self.jules_branch],
                check=True,
                capture_output=True,
            )
            print(f"✅ Synced '{self.jules_branch}' with main")
            return None  # No drift
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            print(f"⚠️  Sync failed: {stderr}. Treating as drift...")
            return self._rotate_drifted_branch()  # Creates jules-sprint-N and PR automatically


class PRManager:
    """Handles GitHub PR operations."""

    def __init__(self, jules_branch: str = JULES_BRANCH):
        """Initialize PR manager.

        Args:
            jules_branch: Name of the Jules integration branch (for merges)
        """
        self.jules_branch = jules_branch

    def is_draft(self, pr_details: dict) -> bool:
        """Check if a PR is a draft.

        Args:
            pr_details: PR details from GitHub API

        Returns:
            True if PR is a draft, False otherwise
        """
        # Check both field names for compatibility
        return pr_details.get("is_draft", False) or pr_details.get("isDraft", False)

    def mark_ready(self, pr_number: int) -> None:
        """Mark a draft PR as ready for review.

        Args:
            pr_number: PR number to mark as ready

        Raises:
            MergeError: If marking ready fails
        """
        try:
            subprocess.run(
                ["gh", "pr", "ready", str(pr_number)],
                check=True,
                capture_output=True,
            )
            print(f"✅ Marked PR #{pr_number} as ready for review.")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            raise MergeError(f"Failed to mark PR #{pr_number} as ready: {stderr}") from e

    def is_green(self, pr_details: dict) -> bool:
        """Check if all CI checks on a PR are passing.

        Args:
            pr_details: PR details from GitHub API

        Returns:
            True if all checks pass (or no checks exist)
        """
        mergeable = pr_details.get("mergeable")
        if mergeable is None:
            print(f"⏳ PR #{pr_details.get('number')} mergeability is UNKNOWN. Waiting...")
            return False
        if mergeable is False:
            print(f"❌ PR #{pr_details.get('number')} is NOT mergeable (conflicts).")
            return False

        status_checks = pr_details.get("statusCheckRollup", [])
        if not status_checks:
            print("✅ No status checks found.")
            return True

        all_passing = True
        for check in status_checks:
            name = check.get("context") or check.get("name") or "Unknown"
            status = (check.get("conclusion") or check.get("status") or check.get("state") or "").upper()

            if status in ["SUCCESS", "NEUTRAL", "SKIPPED", "COMPLETED"]:
                print(f"✅ {name}: {status}")
            else:
                print(f"⏳ {name}: {status} (PENDING/FAILED)")
                all_passing = False

        return all_passing

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception(lambda e: isinstance(e, MergeError) and "permission denied" not in str(e).lower() and "403" not in str(e).lower()),
        reraise=True
    )
    def merge_into_jules(self, pr_number: int) -> None:
        """Merge a PR into the Jules branch using gh CLI.

        First retargets the PR to the jules branch (in case it was created
        with a different base like main), then performs the merge.

        Args:
            pr_number: PR number to merge

        Raises:
            MergeError: If merge fails
        """
        try:
            # Retarget PR to jules branch to ensure proper merge flow
            subprocess.run(
                ["gh", "pr", "edit", str(pr_number), "--base", self.jules_branch],
                check=True,
                capture_output=True,
            )
            print(f"Retargeted PR #{pr_number} to '{self.jules_branch}'.")

            # Merge the PR
            subprocess.run(
                ["gh", "pr", "merge", str(pr_number), "--merge", "--delete-branch"],
                check=True,
                capture_output=True,
            )
            print(f"Successfully merged PR #{pr_number} into '{self.jules_branch}'.")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            raise MergeError(f"Failed to merge PR #{pr_number}: {stderr}") from e

    def ensure_integration_pr_exists(self, repo_info: dict[str, Any]) -> int | None:
        """Ensure a PR exists from jules branch to main for human review.

        Creates a PR if:
        - jules branch exists
        - jules is ahead of main (has commits to merge)
        - No open PR from jules to main exists

        Args:
            repo_info: Repository information (owner, repo)

        Returns:
            PR number if PR exists or was created, None if not needed
        """
        try:
            # Check if PR already exists: jules → main
            import json

            result = subprocess.run(
                ["gh", "pr", "list", "--head", self.jules_branch, "--base", "main", "--json", "number"],
                capture_output=True,
                text=True,
                check=True,
            )
            prs = json.loads(result.stdout) if result.stdout.strip() else []

            if prs:
                pr_number = prs[0]["number"]
                print(f"ℹ️  Integration PR #{pr_number} already exists: {self.jules_branch} → main")
                return pr_number

            # Check if jules is ahead of main
            ahead_result = subprocess.run(
                ["git", "rev-list", "--count", f"origin/main..origin/{self.jules_branch}"],
                capture_output=True,
                text=True,
                check=True,
            )
            commits_ahead = int(ahead_result.stdout.strip())

            if commits_ahead == 0:
                print(f"ℹ️  Branch '{self.jules_branch}' is in sync with main. No PR needed.")
                return None

            # Create PR: jules → main using GitHub API (avoids GH Actions restrictions)
            print(f"📝 Creating integration PR: {self.jules_branch} → main ({commits_ahead} commits)")

            from jules.github import GitHubClient

            pr_title = f"🤖 Integration: {self.jules_branch} → main"
            pr_body = f"""## Automated Integration PR

This PR contains accumulated work from the Jules autonomous development cycle.

**Stats**:
- Commits: {commits_ahead}
- Source: `{self.jules_branch}`
- Target: `main`

**Review Instructions**:
1. Review the accumulated changes from persona iterations
2. Verify all CI checks pass
3. Merge when ready to integrate into main branch

**Note**: This PR is automatically maintained by the Jules scheduler. New commits will be added as personas complete their work.
"""

            github_client = GitHubClient()
            pr_data = github_client.create_pull_request(
                owner=repo_info["owner"],
                repo=repo_info["repo"],
                title=pr_title,
                body=pr_body,
                head=self.jules_branch,
                base="main",
            )

            if pr_data:
                pr_number = pr_data["number"]
                pr_url = pr_data["html_url"]
                print(f"✅ Created integration PR #{pr_number}: {pr_url}")
                return pr_number
            else:
                print("⚠️  Failed to create integration PR via GitHub API")
                return None

        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            print(f"⚠️  Failed to ensure integration PR: {stderr}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"⚠️  Error in ensure_integration_pr_exists: {e}", file=sys.stderr)
            return None

    def find_by_session_id(
        self, open_prs: list[dict[str, Any]], session_id: str
    ) -> dict[str, Any] | None:
        """Find a PR matching the given session ID.

        Args:
            open_prs: List of open PRs from GitHub API
            session_id: Jules session ID to search for

        Returns:
            PR dict if found, None otherwise
        """
        for pr in open_prs:
            head_ref = pr.get("headRefName", "")
            body = pr.get("body", "") or ""
            extracted_id = _extract_session_id(head_ref, body)
            if extracted_id == session_id:
                return pr
        return None


class CycleStateManager:
    """Manages cycle state and progression logic."""

    def __init__(self, cycle_personas: list[PersonaConfig]):
        """Initialize cycle state manager.

        Args:
            cycle_personas: Ordered list of personas in the cycle
        """
        self.cycle_personas = cycle_personas
        self.cycle_ids = [p.id for p in cycle_personas]

    def find_last_cycle_session(
        self,
        client: JulesClient,
        repo_info: dict[str, Any],
        open_prs: list[dict[str, Any]],
    ) -> CycleState:
        """Find the most recent cycle session and determine next state.

        Args:
            client: Jules API client
            repo_info: Repository information
            open_prs: List of open PRs

        Returns:
            CycleState representing current cycle position
        """
        # Get all sessions sorted by creation time
        response = client.list_sessions()
        sessions = response.get("sessions", [])
        sessions_sorted = sorted(sessions, key=lambda s: s.get("createTime", ""), reverse=True)

        # Find most recent cycle session
        for session in sessions_sorted:
            session_name = session.get("name", "")
            session_id = session_name.split("/")[-1] if session_name else None
            if not session_id:
                continue

            # Try to find PR for this session
            pr = None
            for open_pr in open_prs:
                head_ref = open_pr.get("headRefName", "")
                body = open_pr.get("body", "") or ""
                extracted_id = _extract_session_id(head_ref, body)
                if extracted_id == session_id:
                    pr = open_pr
                    break

            # If not in open PRs, check all states
            if not pr:
                pr = get_pr_by_session_id_any_state(
                    repo_info["owner"], repo_info["repo"], session_id
                )

            if not pr:
                continue

            # Check if this is a scheduler branch (from head, not base)
            head_branch = pr.get("headRefName", "") or ""
            if not head_branch.lower().startswith(f"{JULES_SCHEDULER_PREFIX}-"):
                continue

            # Extract persona from head branch
            persona_id = self._match_persona_from_branch(head_branch)
            if persona_id:
                # Found last cycle session!
                next_idx, should_increment = self.advance_cycle(persona_id)
                return CycleState(
                    last_session_id=session_id,
                    last_persona_id=persona_id,
                    next_persona_id=self.cycle_ids[next_idx],
                    next_persona_index=next_idx,
                    should_increment_sprint=should_increment,
                    base_pr_number=str(pr.get("number", "")),
                )

        # No history found - start fresh
        return CycleState(
            last_session_id=None,
            last_persona_id=None,
            next_persona_id=self.cycle_ids[0],
            next_persona_index=0,
            should_increment_sprint=False,
            base_pr_number="",
        )

    def advance_cycle(self, current_persona: str) -> tuple[int, bool]:
        """Calculate next persona index and sprint increment flag.

        Args:
            current_persona: ID of the persona that just completed

        Returns:
            Tuple of (next_index, should_increment_sprint)
        """
        if current_persona not in self.cycle_ids:
            return 0, False

        current_idx = self.cycle_ids.index(current_persona)
        next_idx = (current_idx + 1) % len(self.cycle_ids)
        should_increment = next_idx == 0  # Completed full cycle

        return next_idx, should_increment

    def _match_persona_from_branch(self, branch_name: str) -> str | None:
        """Extract persona ID from branch name.

        Args:
            branch_name: Git branch name

        Returns:
            Persona ID if found, None otherwise
        """
        branch_lower = branch_name.lower()
        for persona_id in self.cycle_ids:
            pid_lower = persona_id.lower()
            pattern = rf"(?:^|[-_/]){re.escape(pid_lower)}(?:$|[-_/])"
            if re.search(pattern, branch_lower):
                return persona_id
        return None


class SessionOrchestrator:
    """Coordinates Jules session creation."""

    def __init__(self, client: JulesClient, dry_run: bool = False):
        """Initialize session orchestrator.

        Args:
            client: Jules API client
            dry_run: If True, don't actually create sessions
        """
        self.client = client
        self.dry_run = dry_run

    def create_session(self, request: SessionRequest) -> str:
        """Create a Jules session.

        Args:
            request: Session creation parameters

        Returns:
            Session ID (or "[DRY RUN]" in dry run mode)
        """
        if self.dry_run:
            print(
                f"[Dry Run] Would create session for {request.persona_id} on branch '{request.branch}'"
            )
            return "[DRY RUN]"

        result = self.client.create_session(
            prompt=request.prompt,
            owner=request.owner,
            repo=request.repo,
            branch=request.branch,
            title=request.title,
            automation_mode=request.automation_mode,
            require_plan_approval=request.require_plan_approval,
        )

        session_id = result.get("name", "").split("/")[-1]
        print(f"Created session {request.persona_id}: {session_id}")
        return session_id

    def handle_stuck_session(self, session_id: str, session_created_at: str | None = None) -> bool:
        """Handle a session that is stuck waiting for user input.

        Args:
            session_id: Session ID to check and potentially nudge
            session_created_at: ISO timestamp when session was created (from cycle state)

        Returns:
            bool: True if session should be skipped, False if should keep waiting
        """
        if self.dry_run:
            print(f"[Dry Run] Would check/nudge session {session_id}")
            return False

        try:
            session_details = self.client.get_session(session_id)
            state = session_details.get("state")

            # Calculate elapsed time if we have creation timestamp
            elapsed_hours = None
            # Try to get creation time from passed parameter first
            if session_created_at:
                try:
                    created = datetime.fromisoformat(session_created_at.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    elapsed = now - created
                    elapsed_hours = elapsed.total_seconds() / 3600.0
                except (ValueError, AttributeError):
                    pass

            # If not available, try to get it from session details API response
            if elapsed_hours is None and "createTime" in session_details:
                try:
                    created = datetime.fromisoformat(session_details["createTime"].replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    elapsed = now - created
                    elapsed_hours = elapsed.total_seconds() / 3600.0
                except (ValueError, AttributeError, KeyError):
                    pass

            # Check for timeout on IN_PROGRESS sessions
            if state == "IN_PROGRESS" and elapsed_hours is not None:
                if elapsed_hours > SESSION_TIMEOUT_HOURS:
                    print(f"⏰ Session {session_id} stuck IN_PROGRESS for {elapsed_hours:.1f}h (>{SESSION_TIMEOUT_HOURS}h threshold)")
                    print(f"   Marking session as timed out. Skipping to next persona...")
                    return True  # Skip this session
                else:
                    print(f"Session {session_id} state: IN_PROGRESS ({elapsed_hours:.1f}h elapsed, waiting...)")
                    return False

            # Check for timeout on COMPLETED/FAILED sessions without PR
            if state in ["COMPLETED", "FAILED"] and elapsed_hours is not None:
                if elapsed_hours > SESSION_TIMEOUT_HOURS:
                    print(f"⏰ Session {session_id} stuck in {state} for {elapsed_hours:.1f}h without PR (>{SESSION_TIMEOUT_HOURS}h threshold)")
                    print(f"   Marking session as timed out. Skipping to next persona...")
                    return True  # Skip this session
                else:
                    print(f"Session {session_id} state: {state} ({elapsed_hours:.1f}h elapsed, no PR yet...)")
                    return False

            if state == "AWAITING_PLAN_APPROVAL":
                print(f"Session {session_id} is awaiting plan approval. Approving automatically...")
                self.client.approve_plan(session_id)
                return False

            elif state == "AWAITING_USER_FEEDBACK":
                print(f"Session {session_id} is awaiting user feedback (stuck). Sending nudge...")
                nudge_text = (
                    "Please make the best decision possible and proceed autonomously "
                    "to complete the task."
                )
                self.client.send_message(session_id, nudge_text)
                print(f"Nudge sent to session {session_id}.")
                return False

            else:
                elapsed_str = f" ({elapsed_hours:.1f}h elapsed)" if elapsed_hours is not None else ""
                print(f"Session {session_id} state: {state}{elapsed_str}. Waiting.")
                return False

        except Exception as e:
            print(f"Error checking/approving session {session_id}: {e}", file=sys.stderr)
            return False


class ReconciliationManager:
    """Manages drift reconciliation using Jules sessions."""

    def __init__(
        self,
        client: JulesClient,
        repo_info: dict[str, Any],
        jules_branch: str = JULES_BRANCH,
        dry_run: bool = False,
    ):
        """Initialize reconciliation manager.

        Args:
            client: Jules API client
            repo_info: Repository information (owner, repo)
            jules_branch: Name of the Jules integration branch
            dry_run: If True, don't actually create sessions
        """
        self.client = client
        self.repo_info = repo_info
        self.jules_branch = jules_branch
        self.dry_run = dry_run

    def reconcile_drift(self, drift_pr_number: int, sprint_number: int) -> str | None:
        """Create a Jules session to reconcile drifted changes.

        Args:
            drift_pr_number: PR number of the drift backup (jules-sprint-N)
            sprint_number: Sprint number for naming

        Returns:
            Session ID of reconciliation session, or None if failed/dry-run
        """
        from jules.github import GitHubClient

        tracker = ReconciliationTracker()
        if not tracker.can_reconcile(sprint_number):
            print(
                f"⚠️  Reconciliation already attempted for sprint {sprint_number}. "
                "Skipping to avoid loops."
            )
            return None

        print(f"\n🔄 Creating reconciliation session for drift PR #{drift_pr_number}...")

        # Get the PR diff
        gh_client = GitHubClient()
        diff = gh_client.get_pr_diff(
            self.repo_info["owner"], self.repo_info["repo"], drift_pr_number
        )

        if not diff:
            print(f"❌ Could not fetch diff for PR #{drift_pr_number}. Skipping reconciliation.")
            return None

        # Truncate diff if too large (Jules has prompt limits)
        MAX_DIFF_SIZE = 50000  # characters
        if len(diff) > MAX_DIFF_SIZE:
            print(
                f"⚠️  Diff is large ({len(diff)} chars). Truncating to {MAX_DIFF_SIZE} chars..."
            )
            diff = diff[:MAX_DIFF_SIZE] + "\n\n[...diff truncated due to size...]"

        # Create reconciliation prompt
        prompt = f"""**Drift Reconciliation - Sprint {sprint_number}**

The `jules` branch diverged from `main` and was backed up to `jules-sprint-{sprint_number}`.

Your task is to reconcile the drifted changes with the current `main` branch.

**Backup PR**: #{drift_pr_number}
**Drift diff** (changes that need reconciliation):

```diff
{diff}
```

**Instructions**:
1. Review the diff carefully to understand what changed in the drifted branch
2. Apply these changes to the current codebase in a reconciliatory manner:
   - Resolve any conflicts with current code
   - Preserve the intent of the original changes
   - Ensure code quality and consistency
3. If changes are no longer relevant or conflict irreconcilably, document why in the PR
4. Create a Pull Request with the reconciled changes

**Important**: This is a reconciliation task. Be thoughtful about merging old changes with new code."""

        title = f"[Reconciliation] Sprint {sprint_number} drift"

        if self.dry_run:
            print(f"[Dry Run] Would create reconciliation session")
            print(f"  Prompt: {prompt[:200]}...")
            print(f"  Base branch: {self.jules_branch}")
            return "[DRY RUN]"

        # Create the session
        try:
            result = self.client.create_session(
                prompt=prompt,
                owner=self.repo_info["owner"],
                repo=self.repo_info["repo"],
                branch=self.jules_branch,
                title=title,
                automation_mode="AUTO_CREATE_PR",
                require_plan_approval=False,
            )

            session_id = result.get("name", "").split("/")[-1]
            print(f"✅ Created reconciliation session: {session_id}")
            tracker.mark_reconciled(sprint_number, session_id)
            return session_id

        except Exception as e:
            print(f"❌ Failed to create reconciliation session: {e}", file=sys.stderr)
            return None
