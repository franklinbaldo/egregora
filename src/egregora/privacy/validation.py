"""Privacy validation for MESSAGE_SCHEMA tables.

This module enforces privacy requirements for the new MESSAGE_SCHEMA:
1. No raw author names (author_raw, author_name, etc.) in table
2. All authors are anonymized (8-char hex format)

The privacy boundary is at the input adapter: raw names must be anonymized
immediately and never persisted or passed to LLMs.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ibis.expr.types import Table


class PrivacyError(Exception):
    """Raised when privacy validation fails."""


def validate_privacy(table: Table) -> None:
    """Ensure table has no privacy leaks (NEW_MESSAGE_SCHEMA).

    Validates:
    1. No forbidden columns (author_raw, author_name, real_name, user_name)
    2. All authors are anonymized (8-char hex format)

    Args:
        table: Ibis Table to validate

    Raises:
        PrivacyError: If privacy leaks detected

    Example:
        >>> table = adapter.parse(zip_path)
        >>> validate_privacy(table)  # Raises if raw names present

    """
    schema = table.schema()

    # Check 1: No forbidden columns
    forbidden_columns = ["author_raw", "author_name", "real_name", "user_name"]
    found_forbidden = [col for col in forbidden_columns if col in schema.names]

    if found_forbidden:
        msg = f"Privacy leak: forbidden columns found: {found_forbidden}"
        raise PrivacyError(msg)

    # Check 2: Verify all authors are anonymized (8-char hex)
    if "author" not in schema.names:
        return  # No author column, skip check

    authors_df = table.select("author").distinct().execute()
    authors = authors_df["author"].dropna().tolist()

    hex_pattern = re.compile(r"^[0-9a-f]{8}$")
    sentinel_authors = {"system"}

    non_anonymized = [
        author for author in authors if author not in sentinel_authors and not hex_pattern.match(author)
    ]

    if non_anonymized:
        # Show first 5 for debugging
        sample = non_anonymized[:5]
        msg = f"Privacy leak: non-anonymized authors found: {sample}..."
        raise PrivacyError(msg)


__all__ = ["PrivacyError", "validate_privacy"]
