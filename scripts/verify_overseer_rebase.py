import os
import sys

# Add .team to path
sys.path.append(os.path.abspath(".team"))

from repo.core.github import get_repo_info
from repo.scheduler.managers import PRManager


def verify_rebase():
    print("🚀 Starting Overseer Rebase Verification...")

    # Setup
    repo_info = get_repo_info()
    mgr = PRManager("jules")

    # We don't have a real JulesClient authenticated in this script context easily
    # unless we mock it or use the one from env.
    # But reconcile_all_jules_prs takes a client.
    # Actually, we can use a dummy client since we just need GH CLI calls which use `subprocess`.
    # The client is passed but might not be used for *merging*, only for status updates?
    # Let's check usages of client in reconcile_all_jules_prs.

    class DummyClient:
        def list_sessions(self):
            return {"sessions": []}

    client = DummyClient()

    print("🔍 Reconciling PRs...")
    conflict_prs = mgr.reconcile_all_jules_prs(client, repo_info, dry_run=False)

    print(f"🏁 Finished. Conflicts found: {len(conflict_prs)}")
    if conflict_prs:
        print("Conflicts:", conflict_prs)


if __name__ == "__main__":
    verify_rebase()
