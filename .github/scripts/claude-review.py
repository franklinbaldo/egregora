#!/usr/bin/env python3
"""
Claude Code Review Script
Analyzes PR changes and posts review comments using Claude.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

import anthropic

# Configuration
MAX_FILES_TO_REVIEW = 20
MAX_FILE_SIZE = 10000  # characters
IGNORED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip', '.lock'}
IGNORED_PATHS = {'node_modules/', '.git/', '__pycache__/', '.pytest_cache/'}

def run_command(cmd: Sequence[str]) -> str:
    """Run a subprocess command safely and return its output."""

    if not cmd or not all(isinstance(part, str) for part in cmd):
        raise ValueError("Command must be a non-empty sequence of strings")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        printable = " ".join(cmd)
        print(f"Command failed: {printable}")
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip()

_VALID_REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


def _validate_git_ref(ref: str) -> str:
    if not _VALID_REF_RE.fullmatch(ref):
        raise ValueError(f"Unsafe git ref: {ref!r}")
    return ref


def _validate_pr_number(value: str) -> str:
    if not value.isdigit():
        raise ValueError(f"Invalid PR number: {value!r}")
    return value


def get_pr_diff(base_branch: str) -> str:
    """Get the full diff for the PR."""

    # Get diff between base and head
    diff = run_command(["git", "diff", f"origin/{base_branch}...HEAD"])
    return diff

def get_changed_files(base_branch: str) -> List[str]:
    """Get list of changed files in the PR."""

    # Get list of changed files
    files = run_command(["git", "diff", "--name-only", f"origin/{base_branch}...HEAD"])
    return [f.strip() for f in files.split('\n') if f.strip()]

def should_review_file(file_path: str) -> bool:
    """Check if file should be reviewed."""
    
    # Skip if file doesn't exist (deleted files)
    if not Path(file_path).exists():
        return False
    
    # Skip ignored extensions
    if any(file_path.endswith(ext) for ext in IGNORED_EXTENSIONS):
        return False
    
    # Skip ignored paths
    if any(ignored in file_path for ignored in IGNORED_PATHS):
        return False
    
    # Skip if file is too large
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if len(content) > MAX_FILE_SIZE:
                print(f"Skipping {file_path} - too large ({len(content)} chars)")
                return False
    except (UnicodeDecodeError, IOError):
        # Skip binary files or files we can't read
        return False
    
    return True

def get_file_content(file_path: str) -> str:
    """Get content of a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except (UnicodeDecodeError, IOError):
        return f"[Binary file or read error: {file_path}]"

def create_review_prompt(pr_info: Dict[str, str], changed_files: List[str], diff: str) -> str:
    """Create the prompt for Claude to review the code."""
    
    # Limit diff size to avoid token limits
    if len(diff) > 50000:
        diff = diff[:50000] + "\n\n[... diff truncated due to length ...]"
    
    prompt = f"""
You are an expert code reviewer for the Egregora project - a WhatsApp-to-post pipeline with AI enrichment and RAG capabilities.

## PR Information
- **Title**: {pr_info['title']}
- **Target Branch**: {pr_info['base_branch']}
- **Source Branch**: {pr_info['head_branch']}
- **Review Type**: {pr_info['review_type']}

## Changed Files ({len(changed_files)} files)
{chr(10).join(f"- {f}" for f in changed_files[:10])}
{f"... and {len(changed_files) - 10} more files" if len(changed_files) > 10 else ""}

## Full Diff
```diff
{diff}
```

## Review Guidelines

Please provide a thorough code review focusing on:

### 1. Security & Privacy
- **Critical**: Check for privacy violations (phone numbers, PII exposure)
- Verify anonymization is properly applied
- Check for hardcoded secrets or sensitive data
- Validate input sanitization

### 2. Architecture & Design
- Consistency with existing patterns
- Proper separation of concerns
- Integration with Polars DataFrame pipeline
- Configuration management (TOML, env vars)

### 3. Code Quality
- Python best practices and idioms
- Type hints and documentation
- Error handling and edge cases
- Performance considerations

### 4. Egregora-Specific
- WhatsApp parsing correctness
- AI/LLM integration patterns
- RAG and embedding workflows
- Media extraction and handling
- Multi-language support (pt-BR, en-US)

### 5. Dependencies & Testing
- Appropriate use of dependencies
- Test coverage for new features
- Compatibility with existing test suite

## Output Format

Provide your review as:

1. **Overall Assessment** (Approve/Request Changes/Comment)
2. **Security Concerns** (if any - mark as 🔒 CRITICAL)
3. **Major Issues** (blocking problems)
4. **Minor Issues** (improvements)
5. **Positive Feedback** (good practices)

Be concise but thorough. Focus on actionable feedback.
For security issues, be very explicit about the risk.
"""
    
    return prompt

def call_claude(prompt: str) -> str:
    """Call Claude API for code review."""
    
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)
    
    client = anthropic.Anthropic(api_key=api_key)
    
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.1,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        return response.content[0].text
        
    except Exception as e:
        print(f"Error calling Claude API: {e}")
        sys.exit(1)

def post_review_comment(review: str, *, pr_number: str, review_type: str) -> None:
    """Post the review as a PR comment."""

    # Format the comment
    comment = f"""
## 🤖 Claude Code Review ({review_type})

{review}

---
*Automated review by Claude 3.5 Sonnet* • [Workflow](../../actions/workflows/claude-code-review.yml)
"""
    
    # Post comment using GitHub CLI without shell interpolation
    run_command(["gh", "pr", "comment", pr_number, "--body", comment])
    print(f"✅ Posted review comment to PR #{pr_number}")

def main():
    """Main function."""
    
    print("🤖 Starting Claude Code Review...")
    
    # Get environment variables
    required_vars = ['PR_NUMBER', 'BASE_BRANCH', 'HEAD_BRANCH', 'PR_TITLE', 'REVIEW_TYPE']
    for var in required_vars:
        if not os.environ.get(var):
            print(f"Error: {var} environment variable not set")
            sys.exit(1)

    try:
        pr_number = _validate_pr_number(os.environ['PR_NUMBER'])
        base_branch = _validate_git_ref(os.environ['BASE_BRANCH'])
        head_branch = _validate_git_ref(os.environ['HEAD_BRANCH'])
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    # Gather PR information
    pr_info = {
        'number': pr_number,
        'base_branch': base_branch,
        'head_branch': head_branch,
        'title': os.environ['PR_TITLE'],
        'review_type': os.environ['REVIEW_TYPE']
    }
    
    print(f"📋 Reviewing PR #{pr_info['number']}: {pr_info['title']}")
    print(f"🎯 Target: {pr_info['base_branch']} ← {pr_info['head_branch']}")
    
    # Get changed files and diff
    changed_files = get_changed_files(base_branch)
    reviewable_files = [f for f in changed_files if should_review_file(f)]
    
    print(f"📁 Changed files: {len(changed_files)} total, {len(reviewable_files)} reviewable")
    
    if len(reviewable_files) > MAX_FILES_TO_REVIEW:
        print(f"⚠️ Too many files to review ({len(reviewable_files)}), limiting to {MAX_FILES_TO_REVIEW}")
        reviewable_files = reviewable_files[:MAX_FILES_TO_REVIEW]
    
    if not reviewable_files:
        print("ℹ️ No reviewable files found, skipping review")
        return
    
    # Get diff
    print("📝 Getting PR diff...")
    diff = get_pr_diff(base_branch)
    
    # Create review prompt
    print("🧠 Preparing Claude prompt...")
    prompt = create_review_prompt(pr_info, reviewable_files, diff)
    
    # Call Claude
    print("🔍 Running Claude analysis...")
    review = call_claude(prompt)
    
    # Post review
    print("💬 Posting review comment...")
    post_review_comment(review, pr_number=pr_number, review_type=os.environ['REVIEW_TYPE'])
    
    print("✅ Code review completed!")

if __name__ == "__main__":
    main()