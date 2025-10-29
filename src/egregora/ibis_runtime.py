"""Compatibility helpers for executing Ibis expressions across versions."""

from __future__ import annotations

from typing import Any, TypeVar

import ibis

__all__ = [
    "execute",
    "execute_scalar",
]

_T = TypeVar("_T")


def execute(expression) -> Any:
    """Execute ``expression`` using Ibis' current default backend."""

    backend = getattr(getattr(ibis, "options", None), "default_backend", None)
    execute_method = getattr(expression, "execute", None)

    if execute_method is not None:
        try:
            return execute_method()
        except TypeError as exc:
            # Older Ibis releases required passing the backend explicitly.
            if "backend" in str(exc) and backend is not None:
                try:
                    return execute_method(backend=backend)
                except TypeError:
                    pass
            else:
                raise

    if backend is not None and hasattr(backend, "execute"):
        return backend.execute(expression)

    if execute_method is None:
        raise RuntimeError("Expression is not executable with the active backend")

    return execute_method()


def execute_scalar(expression) -> _T:
    """Execute scalar expressions with the active backend and normalise values."""

    result = execute(expression)
    if hasattr(result, "item"):
        return result.item()
    return result
