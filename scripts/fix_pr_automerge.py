#!/usr/bin/env python3
"""
Script to manually fix PR auto-merge issues.

This script converts a PR from draft to ready for review and enables auto-merge.
It's useful for fixing PRs where the auto-merge workflow failed silently.

Usage:
    export GITHUB_TOKEN=your_token_here
    python scripts/fix_pr_automerge.py 1688
"""

import os
import sys

import requests


def fix_pr(pr_number: int, token: str, owner: str = "franklinbaldo", repo: str = "egregora"):
    """Fix a PR by converting from draft and enabling auto-merge."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    print(f"🔍 Checking PR #{pr_number}...")

    # Get PR details
    pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    response = requests.get(pr_url, headers=headers)
    response.raise_for_status()
    pr_data = response.json()

    print(f"   Title: {pr_data['title']}")
    print(f"   Draft: {pr_data['draft']}")
    print(f"   Auto-merge: {pr_data['auto_merge']}")
    print(f"   Mergeable: {pr_data['mergeable']}")
    print(f"   State: {pr_data['state']}")

    # Convert from draft if needed
    if pr_data["draft"]:
        print("\n📝 Converting from draft to ready for review...")
        update_response = requests.patch(pr_url, headers=headers, json={"draft": False})
        update_response.raise_for_status()
        print("   ✅ Successfully converted from draft")

        # Post comment
        comment_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
        requests.post(
            comment_url,
            headers=headers,
            json={
                "body": "🤖 **Draft converted to ready for review**\n\n"
                "This PR has been manually marked as ready for review via fix script."
            },
        )
    else:
        print("\n   ℹ️  PR is already ready for review")

    # Enable auto-merge if not already enabled
    if pr_data["auto_merge"] is None:
        print("\n🔄 Enabling auto-merge...")
        node_id = pr_data["node_id"]

        graphql_url = "https://api.github.com/graphql"
        mutation = """
        mutation($pullRequestId: ID!) {
            enablePullRequestAutoMerge(input: {
                pullRequestId: $pullRequestId,
                mergeMethod: MERGE
            }) {
                pullRequest {
                    autoMergeRequest {
                        enabledAt
                        enabledBy {
                            login
                        }
                    }
                }
            }
        }
        """

        graphql_response = requests.post(
            graphql_url, headers=headers, json={"query": mutation, "variables": {"pullRequestId": node_id}}
        )
        graphql_response.raise_for_status()
        result = graphql_response.json()

        if "errors" in result:
            print(f"   ❌ GraphQL errors: {result['errors']}")
            sys.exit(1)

        print("   ✅ Auto-merge enabled successfully")

        # Post comment
        comment_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
        requests.post(
            comment_url,
            headers=headers,
            json={
                "body": "🤖 **Auto-merge enabled**\n\n"
                "This PR will automatically merge when all required checks pass.\n\n"
                "_Manually enabled via fix script_"
            },
        )
    else:
        print("\n   ℹ️  Auto-merge is already enabled")

    # Verify the changes
    print("\n🔍 Verifying changes...")
    verify_response = requests.get(pr_url, headers=headers)
    verify_response.raise_for_status()
    verify_data = verify_response.json()

    print(f"   Draft: {verify_data['draft']}")
    print(f"   Auto-merge: {'enabled' if verify_data['auto_merge'] else 'disabled'}")

    if not verify_data["draft"] and verify_data["auto_merge"]:
        print("\n✅ PR is now ready for auto-merge!")
    else:
        print("\n⚠️  PR may still have issues. Check the GitHub UI for details.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/fix_pr_automerge.py <pr_number>")
        sys.exit(1)

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("❌ Error: GITHUB_TOKEN environment variable not set")
        print("Please set it with: export GITHUB_TOKEN=your_token_here")
        sys.exit(1)

    try:
        pr_number = int(sys.argv[1])
        fix_pr(pr_number, token)
    except ValueError:
        print(f"❌ Error: Invalid PR number '{sys.argv[1]}'")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        print(f"   Response: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
