"""Base dispatcher class with shared routing logic for Gemini API calls."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

TRequest = TypeVar("TRequest")
TResult = TypeVar("TResult")


class BaseDispatcher[TRequest, TResult](ABC):
    """Abstract base for intelligent dispatchers that route between batch and individual API calls.

    This class implements the common logic for choosing between batch API operations
    and parallel individual calls based on request count and configuration.

    Subclasses must implement:
    - _execute_one(): Single item execution logic
    - _execute_batch(): Batch execution logic
    """

    def __init__(
        self,
        batch_threshold: int = 10,
        max_parallel: int = 5,
    ) -> None:
        """Initialize dispatcher with routing configuration.

        Args:
            batch_threshold: Minimum number of requests to use batch API
            max_parallel: Maximum parallel workers for individual calls

        """
        self._batch_threshold = batch_threshold
        self._max_parallel = max_parallel

    def dispatch(
        self,
        requests: Sequence[TRequest],
        *,
        force_batch: bool = False,
        force_individual: bool = False,
        **kwargs,
    ) -> list[TResult]:
        """Dispatch requests using the optimal strategy.

        Routes requests to either batch or individual execution based on:
        - Force flags (manual override)
        - Request count vs threshold (automatic decision)

        Args:
            requests: Sequence of requests to execute
            force_batch: Force batch API even for small counts
            force_individual: Force individual calls even for large counts
            **kwargs: Additional parameters to pass to execution methods

        Returns:
            List of results in the same order as requests

        Raises:
            ValueError: If both force flags are True

        """
        if not requests:
            return []

        if force_batch and force_individual:
            msg = "Cannot force both batch and individual strategies"
            raise ValueError(msg)

        # Manual override
        if force_batch:
            logger.info(f"Forcing batch API for {len(requests)} items")
            return self._execute_batch(requests, **kwargs)
        if force_individual:
            logger.info(f"Forcing individual calls for {len(requests)} items")
            return self._execute_individual(requests)

        # Automatic decision based on threshold
        if len(requests) < self._batch_threshold:
            logger.info(f"Using individual calls for {len(requests)} items")
            return self._execute_individual(requests)
        logger.info(f"Using batch API for {len(requests)} items")
        return self._execute_batch(requests, **kwargs)

    def _execute_individual(self, requests: Sequence[TRequest]) -> list[TResult]:
        """Execute requests individually with parallelism.

        Uses ThreadPoolExecutor to run requests in parallel up to max_parallel limit.

        Args:
            requests: Sequence of requests to execute

        Returns:
            List of results in the same order as requests

        """
        with ThreadPoolExecutor(max_workers=self._max_parallel) as executor:
            futures = [executor.submit(self._execute_one, req) for req in requests]
            return [f.result() for f in futures]

    @abstractmethod
    def _execute_one(self, request: TRequest) -> TResult:
        """Execute a single request.

        Subclasses must implement this to handle individual API calls.
        Should include error handling and return a result even on failure.

        Args:
            request: Single request to execute

        Returns:
            Result object (may contain error information)

        """

    @abstractmethod
    def _execute_batch(self, requests: Sequence[TRequest], **kwargs) -> list[TResult]:
        """Execute requests as a batch.

        Subclasses must implement this to handle batch API calls.

        Args:
            requests: Sequence of requests to execute
            **kwargs: Additional parameters (display_name, poll_interval, timeout, etc.)

        Returns:
            List of results in the same order as requests

        """
