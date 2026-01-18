import contextlib
import json
import os
import subprocess
import sys


def main() -> None:
    try:
        pull_requests = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(1)

    for pr in pull_requests:
        pr_number = pr.get("number")
        patch_url = pr.get("patch_url")
        author = pr.get("user", {}).get("login")

        if not pr_number or not patch_url or not author:
            continue

        patch_filename = f"pr_{pr_number}.patch"

        # Download the patch
        try:
            subprocess.run(
                ["curl", "-L", patch_url, "-o", patch_filename], check=True, capture_output=True, text=True
            )
        except subprocess.CalledProcessError:
            continue

        # Apply the patch
        try:
            apply_command = ["git", "apply", "--3way", patch_filename]
            subprocess.run(apply_command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError:
            # Send email notification
            email_subject = f"⚠️ PR #{pr_number}: Conflict Detected"
            email_body = (
                f"Hello @{author},\n\n"
                f"Your PR #{pr_number} has conflicts with the current `jules` branch and could not be merged automatically.\n\n"
                f"Please rebase your branch onto the latest `jules` branch, resolve any conflicts, and push the changes to update your PR.\n\n"
                f"Thank you,\nWeaver 🕸️"
            )

            email_command = [
                "uv",
                "run",
                "my-tools",
                "email",
                "send",
                "--to",
                author,
                "--subject",
                email_subject,
                "--body",
                email_body,
                "--from",
                "weaver",
            ]

            # Setting PYTHONPATH for the email command
            env = os.environ.copy()
            env["PYTHONPATH"] = ".team"

            with contextlib.suppress(subprocess.CalledProcessError):
                subprocess.run(email_command, check=True, capture_output=True, text=True, env=env)

        finally:
            # Clean up the patch file
            if os.path.exists(patch_filename):
                os.remove(patch_filename)


if __name__ == "__main__":
    main()
