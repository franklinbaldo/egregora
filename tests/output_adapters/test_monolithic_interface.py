"""Contract tests for output adapters' monolithic interface."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from egregora.output_adapters.eleventy_arrow.adapter import EleventyArrowOutputAdapter

from egregora.output_adapters.base import OutputAdapter
from egregora.output_adapters.mkdocs import MkDocsAdapter

FORBIDDEN_ATTRIBUTES = {"posts", "profiles", "journals", "enrichments"}


def test_output_adapter_base_exposes_monolithic_contract() -> None:
    """Ensure the abstract base class does not define legacy storage shims."""

    adapter_members = set(OutputAdapter.__dict__.keys())
    overlap = FORBIDDEN_ATTRIBUTES & adapter_members
    assert not overlap, f"OutputAdapter unexpectedly exposes storage helpers: {sorted(overlap)}"


@pytest.mark.parametrize(
    "factory",
    [
        pytest.param(lambda tmp_path: MkDocsAdapter(), id="mkdocs"),
        pytest.param(lambda tmp_path: EleventyArrowOutputAdapter(), id="eleventy-arrow"),
    ],
)
def test_output_adapters_do_not_expose_storage_objects(
    factory: Callable[[Path], OutputAdapter], tmp_path: Path
) -> None:
    """Adapters should rely on the monolithic interface, not storage helpers."""

    adapter = factory(tmp_path)
    adapter.initialize(tmp_path)

    for attribute in FORBIDDEN_ATTRIBUTES:
        assert not hasattr(adapter, attribute), f"Adapter leaks legacy attribute '{attribute}'"
