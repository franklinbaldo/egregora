"""Background task coordination for the write pipeline.

This module handles tasks that run outside the main window processing loop,
such as banner generation, profile consolidation, and taxonomy generation.
"""

from __future__ import annotations

import logging

from egregora.agents.banner.worker import BannerWorker
from egregora.agents.enricher import EnrichmentWorker
from egregora.agents.profile.worker import ProfileWorker
from egregora.ops.taxonomy import generate_semantic_taxonomy
from egregora.orchestration.context import PipelineContext
from egregora.orchestration.pipelines.etl.preparation import PreparedPipelineData

logger = logging.getLogger(__name__)


def process_background_tasks(ctx: PipelineContext) -> None:
    """Process pending background tasks.

    Args:
        ctx: Pipeline context containing task store and configuration.

    """
    if not hasattr(ctx, "task_store") or not ctx.task_store:
        return

    # Banner Generation (Visual identity for posts)
    try:
        banner_worker = BannerWorker(ctx)
        banner_worker.run()
    except Exception as e:
        logger.warning("Banner generation background task failed: %s", e)

    # Profile Consolidation (Update author profiles)
    try:
        profile_worker = ProfileWorker(ctx)
        profile_worker.run()
    except Exception as e:
        logger.warning("Profile worker background task failed: %s", e)

    # Enrichment (If pending items remain)
    if ctx.config.enrichment.enabled:
        try:
            enrichment_worker = EnrichmentWorker(ctx)
            enrichment_worker.run()
        except Exception as e:
            logger.warning("Enrichment worker background task failed: %s", e)


def generate_taxonomy_task(dataset: PreparedPipelineData) -> None:
    """Generate semantic taxonomy if enabled.

    Args:
        dataset: Prepared pipeline data containing context.

    """
    if dataset.context.config.rag.enabled:
        logger.info("[bold cyan]🏷️  Generating Semantic Taxonomy...[/]")
        try:
            tagged_count = generate_semantic_taxonomy(dataset.context.output_sink, dataset.context.config)
            if tagged_count > 0:
                logger.info("[green]✓ Applied semantic tags to %d posts[/]", tagged_count)
        except (ValueError, TypeError, AttributeError) as e:
            # Non-critical failure
            logger.warning("Auto-taxonomy failed: %s", e)
        except Exception as e:
            logger.warning("Unexpected error during taxonomy generation: %s", e)
