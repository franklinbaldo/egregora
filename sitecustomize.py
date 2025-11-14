"""Test helpers to patch optional third-party APIs."""

from __future__ import annotations

try:  # pragma: no cover - best effort patching
    import duckdb
    from types import SimpleNamespace

    if not hasattr(duckdb, "functional"):
        duckdb.functional = SimpleNamespace(ARROW=object(), NATIVE=object())  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - ignore patch failures
    pass
