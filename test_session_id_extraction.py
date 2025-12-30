#!/usr/bin/env python3
"""Test script for session ID extraction logic in the Jules bot."""

import os
import re
import sys
from re import Pattern

# Ensure the .jules directory is in the path
sys.path.insert(0, ".jules")

import jules.github as jules_github


def test_session_id_extraction_from_branch() -> None:
    """Test various branch name patterns for session ID extraction."""
    # Pattern for numeric session IDs (e.g., from Colab)
    numeric_pattern: Pattern[str] = re.compile(r".*-(\d{15,})$")
    # Pattern for UUID-based session IDs
    uuid_pattern: Pattern[str] = re.compile(
        r".*-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
    )

    test_cases = [
        # Numeric ID - Valid
        ("jules-8447861939500903300", "8447861939500903300", numeric_pattern),
        # Numeric ID - Too short
        ("jules-844786193950", None, numeric_pattern),
        # UUID - Valid
        ("jules-123e4567-e89b-12d3-a456-426614174000", "123e4567-e89b-12d3-a456-426614174000", uuid_pattern),
        # UUID - Invalid format
        ("jules-123e4567-e89b-12d3-a456-42661417400", None, uuid_pattern),
        # No ID present
        ("jules-feature-branch", None, None),
    ]

    for branch, expected_id, pattern in test_cases:
        body = ""  # Body is empty for these tests
        session_id = jules_github._extract_session_id(branch, body)

        if expected_id and pattern:
            assert session_id == expected_id, f"Failed on branch: {branch}"  # noqa: S101
            assert pattern.search(branch), f"Pattern {pattern} failed on branch: {branch}"  # noqa: S101
        else:
            assert session_id is None, f"Expected no ID but got {session_id} from branch: {branch}"  # noqa: S101


def test_session_id_extraction_from_body() -> None:
    """Test various PR body patterns for session ID extraction."""
    branch = "jules-some-branch"  # Branch has no ID for these tests

    test_cases = [
        # Jules URL - Valid
        ("Session URL: https://jules.google.com/task/8447861939500903300", "8447861939500903300"),
        # Task URL - Valid
        ("See details at /task/8447861939500903301", "8447861939500903301"),
        # Sessions URL - Valid
        ("Progress tracked in /sessions/8447861939500903302", "8447861939500903302"),
        # No URL in body
        ("This is a standard PR body with no session link.", None),
        # Malformed URL
        ("Linked to /task/ but no ID.", None),
    ]

    for body, expected_id in test_cases:
        session_id = jules_github._extract_session_id(branch, body)
        assert session_id == expected_id, f"Failed on body: {body}"  # noqa: S101


def main() -> int:
    """Run all test cases and print results."""
    # Set environment variable to indicate testing
    os.environ["JULES_TESTING"] = "true"

    # Run tests
    try:
        test_session_id_extraction_from_branch()

        test_session_id_extraction_from_body()

        return 0
    except AssertionError:
        return 1
    finally:
        # Clean up environment variable
        del os.environ["JULES_TESTING"]


if __name__ == "__main__":
    sys.exit(main())
