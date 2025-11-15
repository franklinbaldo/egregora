"""Minimal test stub for the optional `pydantic_ai` dependency.

This project only exercises the public surface area needed to import the
enrichment helpers during unit tests. The actual runtime integrates with the
real library when it is installed; these shims simply keep local test runs
lightweight by providing the handful of symbols that Egregora imports.
"""

from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

DepsT = TypeVar("DepsT")
OutputT = TypeVar("OutputT")


class RunContext(Generic[DepsT]):
    """Tiny stand-in carrying dependency objects for decorators."""

    def __init__(self, deps: DepsT):
        self.deps = deps


class Agent(Generic[DepsT, OutputT]):
    """Bare-bones drop-in replacement for `pydantic_ai.Agent` used in tests."""

    def __init__(self, model: str, output_type: type[Any] | None = None, **kwargs: Any):
        self.model = model
        self.output_type = output_type
        self.kwargs = kwargs

    def system_prompt(self, func: Callable[[RunContext[DepsT]], str]) -> Callable[[RunContext[DepsT]], str]:
        """Return the decorated function unchanged."""

        return func

    def run_sync(self, *args: Any, **kwargs: Any) -> OutputT:
        """Real execution is stubbed out for unit tests."""

        msg = "pydantic_ai stub Agent cannot execute run_sync without the real dependency"
        raise NotImplementedError(msg)


__all__ = ["Agent", "RunContext"]

