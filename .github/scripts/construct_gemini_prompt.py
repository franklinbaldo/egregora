#!/usr/bin/env python3
"""Construct Gemini PR review prompt using Jinja2.

This script reads PR data from files and environment variables,
then renders the Gemini prompt template using Jinja2.
"""

import os
import sys
from pathlib import Path

import jinja2


def main() -> int:
    """Construct and output the Gemini prompt."""
    # Get input paths from environment
    template_path = Path(os.environ.get("TEMPLATE_PATH", ".github/prompts/pr-review-prompt-improved.md"))
    diff_path = Path(os.environ.get("DIFF_PATH", ".github/tmp/diff.txt"))
    claude_md_path = Path(os.environ.get("CLAUDE_MD_PATH", "CLAUDE.md"))
    commits_path = Path(os.environ.get("COMMITS_PATH", ".github/tmp/commits.txt"))
    output_path = Path(os.environ.get("OUTPUT_PATH", ".github/tmp/prompt.txt"))

    # Get PR metadata from environment
    repository = os.environ.get("REPOSITORY", "")
    pr_number = os.environ.get("PR_NUMBER", "")
    pr_title = os.environ.get("PR_TITLE", "")
    pr_author = os.environ.get("PR_AUTHOR", "")
    pr_body = os.environ.get("PR_BODY", "") or "(No description provided)"
    trigger_mode = os.environ.get("TRIGGER_MODE", "automatic")
    user_instructions = os.environ.get("USER_INSTRUCTIONS", "")

    # Read file contents
    try:
        template = template_path.read_text(encoding="utf-8")
        diff = diff_path.read_text(encoding="utf-8") if diff_path.exists() else "(No diff available)"
        claude_md = claude_md_path.read_text(encoding="utf-8") if claude_md_path.exists() else ""
        commits = commits_path.read_text(encoding="utf-8") if commits_path.exists() else "(No commits available)"
    except FileNotFoundError as e:
        print(f"Error: Required file not found: {e.filename}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reading files: {e}", file=sys.stderr)
        return 1

    # Setup Jinja2 environment
    env = jinja2.Environment(
        autoescape=False,  # We're generating markdown, not HTML
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=jinja2.StrictUndefined,
    )

    # Render template
    try:
        template_obj = env.from_string(template)

        # Prepare context
        user_instructions_text = f"**User Request:** {user_instructions}" if user_instructions else ""

        context = {
            "REPOSITORY": repository,
            "PR_NUMBER": pr_number,
            "PR_TITLE": pr_title,
            "PR_AUTHOR": pr_author,
            "PR_BODY": pr_body,
            "TRIGGER_MODE": trigger_mode,
            "USER_INSTRUCTIONS": user_instructions_text,
            "COMMITS": commits,
            "DIFF": diff,
            "CLAUDE_MD": claude_md,
        }

        prompt = template_obj.render(**context)

    except jinja2.TemplateError as e:
        print(f"Error rendering template: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Write output
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(prompt, encoding="utf-8")
        print(f"✓ Prompt written to {output_path} ({len(prompt)} characters)")
    except Exception as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
