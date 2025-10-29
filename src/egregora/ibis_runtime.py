"""Utility helpers for managing a shared Ibis backend without process-global state."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
from threading import RLock
from typing import TYPE_CHECKING, Any, TypeVar

import importlib
import importlib.util

import ibis

_base_spec = importlib.util.find_spec("ibis.backends.base")
if _base_spec is not None:  # pragma: no branch - deterministic import
    BaseBackend = importlib.import_module("ibis.backends.base").BaseBackend
else:  # pragma: no branch - executed on newer Ibis versions
    BaseBackend = importlib.import_module("ibis.backends").BaseBackend

__all__ = [
    "use_backend",
    "get_backend",
    "has_backend",
    "memtable",
    "execute",
    "execute_scalar",
]

_T = TypeVar("_T")


_backend_stack: list[BaseBackend] = []
_stack_lock = RLock()


def _set_ibis_default(backend: BaseBackend | None) -> None:
    """Update ``ibis.options.default_backend`` when available."""

    options = getattr(ibis, "options", None)
    if options is None:
        return

    if backend is None:
        if getattr(options, "default_backend", None) is not None:
            options.default_backend = None
        return

    options.default_backend = backend


@contextmanager
def use_backend(backend: BaseBackend) -> Iterable[BaseBackend]:
    """Activate ``backend`` for the duration of the context."""

    with _stack_lock:
        _backend_stack.append(backend)
        _set_ibis_default(backend)

    try:
        yield backend
    finally:
        with _stack_lock:
            if _backend_stack:
                _backend_stack.pop()
            _set_ibis_default(_backend_stack[-1] if _backend_stack else None)


def get_backend() -> BaseBackend:
    """Return the currently active backend or raise."""

    with _stack_lock:
        if not _backend_stack:
            raise RuntimeError("No active Ibis backend. Wrap calls in use_backend().")
        return _backend_stack[-1]


def has_backend() -> bool:
    """Return ``True`` when a backend is active."""

    with _stack_lock:
        return bool(_backend_stack)


def memtable(data: Any, schema: ibis.Schema | None = None):
    """Create an in-memory table bound to the active backend."""

    backend = get_backend()
    if hasattr(backend, "memtable"):
        return backend.memtable(data, schema=schema)
    # Fallback for older Ibis versions – relies on the default backend
    return ibis.memtable(data, schema=schema)


def execute(expression) -> Any:
    """Execute ``expression`` with the active backend."""

    backend = get_backend()
    execute_method = getattr(expression, "execute", None)

    if execute_method is not None:
        try:
            return execute_method()
        except TypeError as exc:
            # Older Ibis releases required passing the backend explicitly.
            if "backend" in str(exc):
                try:
                    return execute_method(backend=backend)
                except TypeError:
                    pass
            else:
                raise

    if hasattr(backend, "execute"):
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
