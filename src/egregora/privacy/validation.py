"""Privacy validation for MESSAGE_SCHEMA tables.

Ensures no raw author names escape anonymization.
"""

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ibis.expr.types import Table

logger = logging.getLogger(__name__)


class PrivacyError(Exception):
    """Raised when privacy validation fails."""


def validate_privacy(table: "Table") -> None:
    """Ensure table has no privacy leaks.

    Validates:
    1. No forbidden columns exist (author_raw, author_name, real_name)
    2. All author values are anonymized (8-char hex)

    Args:
        table: Ibis Table to validate

    Raises:
        PrivacyError: If privacy validation fails

    Example:
        >>> table = adapter.parse(zip_path)
        >>> validate_privacy(table)  # Raises if leaks found

    """
    schema = table.schema()

    # 1. Check forbidden columns don't exist
    forbidden_columns = ["author_raw", "author_name", "real_name", "user_name"]
    found_forbidden = [col for col in forbidden_columns if col in schema.names]

    if found_forbidden:
        msg = f"Privacy leak: forbidden columns found: {found_forbidden}"
        raise PrivacyError(msg)

    # 2. Verify 'author' column exists
    if "author" not in schema.names:
        msg = "Privacy validation failed: 'author' column missing"
        raise PrivacyError(msg)

    # 3. Verify all authors are anonymized (8-char hex)
    authors_df = table.select("author").distinct().execute()
    authors = authors_df["author"].dropna().tolist()

    hex_pattern = re.compile(r"^[0-9a-f]{8}$")
    non_anonymized = [author for author in authors if not hex_pattern.match(author)]

    if non_anonymized:
        msg = f"Privacy leak: non-anonymized authors found: {non_anonymized[:5]}..."
        raise PrivacyError(msg)

    logger.debug("✅ Privacy validation passed (%d unique authors)", len(authors))


__all__ = ["PrivacyError", "validate_privacy"]
