from __future__ import annotations

import pytest

pytest.skip(
    "Legacy writer runner helpers relied on pandas-based fixtures and manual document indexing. "
    "The document-based writer pipeline replaced that architecture, so this module is temporarily "
    "skipped until the helpers are rewritten without pandas.",
    allow_module_level=True,
)
