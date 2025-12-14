"""Reusable pipeline strategies for error handling and retry logic.

This module encapsulates complex control flow patterns like "split-and-retry"
to keep the main orchestration logic clean and linear.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from egregora.agents.model_limits import PromptTooLargeError
from egregora.transformations import split_window_into_n_parts

if TYPE_CHECKING:
    from egregora.orchestration.context import PipelineContext

logger = logging.getLogger(__name__)

T = TypeVar("T")  # Result type


def process_with_auto_split(
    window: Any,
    ctx: PipelineContext,
    processor_fn: Callable[[Any, PipelineContext, int], dict[str, T]],
    *,
    depth: int = 0,
    max_depth: int = 5,
    min_window_size: int = 5,
) -> dict[str, T]:
    """Process a window with automatic splitting if prompt exceeds model limit.

    This function implements a robust retry strategy:
    1. Try to process the window.
    2. If PromptTooLargeError occurs, split the window into smaller chunks.
    3. Recursively process the chunks.

    Args:
        window: Window object to process
        ctx: Pipeline context passed to processor
        processor_fn: Function to process a single window.
                      Signature: (window, ctx, depth) -> results_dict
        depth: Current recursion depth (0 for initial call)
        max_depth: Maximum recursion depth before failing
        min_window_size: Minimum messages in a window to attempt processing

    Returns:
        Aggregated results dictionary

    Raises:
        RuntimeError: If max_depth is reached or splitting fails

    """
    results: dict[str, T] = {}
    queue: deque[tuple[Any, int]] = deque([(window, depth)])

    while queue:
        current_window, current_depth = queue.popleft()
        indent = "  " * current_depth
        window_label = f"{current_window.start_time:%Y-%m-%d %H:%M} to {current_window.end_time:%H:%M}"

        _warn_if_window_too_small(current_window.size, indent, window_label, min_window_size)
        _ensure_split_depth(current_depth, max_depth, indent, window_label)

        try:
            # Execute the provided processor function
            window_results = processor_fn(current_window, ctx, current_depth)
            results.update(window_results)

        except PromptTooLargeError as error:
            # Calculate required splits based on error details
            split_work = _split_window_for_retry(
                current_window,
                error,
                current_depth,
                indent,
            )
            # Add split parts to the FRONT of the queue (depth-first processing)
            queue.extendleft(reversed(split_work))
            continue

    return results


def _warn_if_window_too_small(size: int, indent: str, label: str, minimum: int) -> None:
    if size < minimum:
        logger.warning(
            "%s⚠️  Window %s too small to split (%d messages) - attempting anyway",
            indent,
            label,
            size,
        )


def _ensure_split_depth(depth: int, max_depth: int, indent: str, label: str) -> None:
    if depth >= max_depth:
        error_msg = (
            f"Max split depth {max_depth} reached for window {label}. "
            "Window cannot be split enough to fit in model context (possible miscalculation). "
            "Try increasing --max-prompt-tokens or using --use-full-context-window."
        )
        logger.error("%s❌ %s", indent, error_msg)
        raise RuntimeError(error_msg)


def _split_window_for_retry(
    window: Any,
    error: Exception,
    depth: int,
    indent: str,
) -> list[tuple[Any, int]]:
    estimated_tokens = getattr(error, "estimated_tokens", 0)
    effective_limit = getattr(error, "effective_limit", 1) or 1

    logger.warning(
        "%s⚡ [yellow]Splitting window[/] %s (prompt: %dk tokens > %dk limit)",
        indent,
        f"{window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}",
        estimated_tokens // 1000,
        effective_limit // 1000,
    )

    num_splits = max(1, math.ceil(estimated_tokens / effective_limit))
    logger.info("%s↳ [dim]Splitting into %d parts[/]", indent, num_splits)

    split_windows = split_window_into_n_parts(window, num_splits)
    if not split_windows:
        error_msg = (
            f"Cannot split window {window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}"
            " - all splits would be empty"
        )
        logger.exception("%s❌ %s", indent, error_msg)
        raise RuntimeError(error_msg) from error

    scheduled: list[tuple[Any, int]] = []
    for index, split_window in enumerate(split_windows, 1):
        split_label = f"{split_window.start_time:%Y-%m-%d %H:%M} to {split_window.end_time:%H:%M}"
        logger.info(
            "%s↳ [dim]Processing part %d/%d: %s[/]",
            indent,
            index,
            len(split_windows),
            split_label,
        )
        scheduled.append((split_window, depth + 1))

    return scheduled
