"""Tests for privacy validation checks on MESSAGE_SCHEMA tables."""

import ibis
import pytest

from egregora.privacy.validation import PrivacyError, validate_privacy


def test_validate_privacy_allows_system_author() -> None:
    """System sentinel authors should bypass anonymization regex."""

    table = ibis.memtable([{"author": "system"}])

    # Should not raise because "system" is an allowed sentinel author
    validate_privacy(table)


def test_validate_privacy_rejects_non_hex_author() -> None:
    """Any other non-hex author should still be rejected."""

    table = ibis.memtable([{"author": "not_hex"}])

    with pytest.raises(PrivacyError):
        validate_privacy(table)
