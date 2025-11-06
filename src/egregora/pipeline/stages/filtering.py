"""Filtering stage - removes unwanted messages from the pipeline.

This stage handles:
- Removing /egregora command messages
- Filtering out opted-out users
- Applying date range filters
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from egregora.agents.tools.profiler import filter_opted_out_authors
from egregora.ingestion.parser import filter_egregora_messages
from egregora.pipeline.base import PipelineStage, StageConfig, StageResult

if TYPE_CHECKING:
    from ibis.expr.types import Table
logger = logging.getLogger(__name__)
__all__ = ["FilteringStage", "FilteringStageConfig"]


class FilteringStageConfig(StageConfig):
    """Configuration for the filtering stage."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        profiles_dir: Any = None,
        from_date: Any = None,
        to_date: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(enabled=enabled, **kwargs)
        self.profiles_dir = profiles_dir
        self.from_date = from_date
        self.to_date = to_date


class FilteringStage(PipelineStage):
    """Filter unwanted messages and apply date range constraints.

    This stage:
    1. Removes all /egregora command messages
    2. Filters out messages from opted-out users
    3. Applies date range filtering (if configured)
    """

    def __init__(self, config: FilteringStageConfig) -> None:
        super().__init__(config)
        if not isinstance(config, FilteringStageConfig):
            msg = f"Expected FilteringStageConfig, got {type(config)}"
            raise TypeError(msg)
        self.filter_config = config

    @property
    def stage_name(self) -> str:
        return "Message Filtering"

    @property
    def stage_identifier(self) -> str:
        return "filtering"

    def process(self, data: Table, _context: dict[str, Any]) -> StageResult:
        """Filter unwanted messages from the table.

        Args:
            data: Input table with messages
            context: Pipeline context (unused for this stage)

        Returns:
            StageResult with filtered table and metrics

        """
        original_count = data.count().execute()
        metrics = {"messages_in": original_count}
        data, egregora_removed = filter_egregora_messages(data)
        if egregora_removed:
            logger.info("[yellow]🧹 Removed[/] %s /egregora messages", egregora_removed)
        metrics["egregora_messages_removed"] = egregora_removed
        if self.filter_config.profiles_dir:
            data, removed_count = filter_opted_out_authors(data, self.filter_config.profiles_dir)
            if removed_count > 0:
                logger.warning("⚠️  %s messages removed from opted-out users", removed_count)
            metrics["opted_out_messages_removed"] = removed_count
        else:
            metrics["opted_out_messages_removed"] = 0
        from_date = self.filter_config.from_date
        to_date = self.filter_config.to_date
        if from_date or to_date:
            pre_date_filter_count = data.count().execute()
            if from_date and to_date:
                data = data.filter((data.timestamp.date() >= from_date) & (data.timestamp.date() <= to_date))
                logger.info("📅 [cyan]Filtering[/] messages from %s to %s", from_date, to_date)
            elif from_date:
                data = data.filter(data.timestamp.date() >= from_date)
                logger.info("📅 [cyan]Filtering[/] messages from %s onwards", from_date)
            elif to_date:
                data = data.filter(data.timestamp.date() <= to_date)
                logger.info("📅 [cyan]Filtering[/] messages up to %s", to_date)
            post_date_filter_count = data.count().execute()
            removed_by_date = pre_date_filter_count - post_date_filter_count
            metrics["date_filtered_messages_removed"] = removed_by_date
            if removed_by_date > 0:
                logger.info(
                    "🗓️  [yellow]Filtered out[/] %s messages by date (kept %s)",
                    removed_by_date,
                    post_date_filter_count,
                )
            else:
                logger.info(
                    "[green]✓ All[/] %s messages are within the specified date range", post_date_filter_count
                )
        else:
            metrics["date_filtered_messages_removed"] = 0
        final_count = data.count().execute()
        metrics["messages_out"] = final_count
        total_removed = original_count - final_count
        logger.info(
            "[green]✓ Filtering complete:[/] %s messages remaining (%s removed)", final_count, total_removed
        )
        return StageResult(data=data, metrics=metrics, modified=total_removed > 0)
