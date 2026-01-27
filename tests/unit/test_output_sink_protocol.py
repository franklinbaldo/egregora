from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from egregora.output_sinks.mkdocs.adapter import MkDocsAdapter

if TYPE_CHECKING:
    from pathlib import Path


def test_finalize_window_signature(tmp_path: Path) -> None:
    """Verify that a concrete OutputSink's finalize_window can be called.

    This acts as a regression test to ensure the method signature is stable
    before and after the refactoring to remove unused parameters.
    """
    # Arrange
    adapter = MkDocsAdapter()
    adapter.initialize(site_root=tmp_path)

    # Act & Assert
    try:
        adapter.finalize_window(
            window_label="test_window",
            _posts_created=["post1"],
            profiles_updated=["profile1"],
            metadata={},
        )
    except TypeError as e:
        pytest.fail(f"finalize_window call failed with unexpected exception: {e}")
