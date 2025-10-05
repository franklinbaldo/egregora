"""Unified processor with Polars-based message manipulation."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from .cache_manager import CacheManager
from .config import PipelineConfig
from .enrichment import ContentEnricher
from .generator import NewsletterContext, NewsletterGenerator
from .group_discovery import discover_groups
from .merger import create_virtual_groups, get_merge_stats
from .models import GroupSource
from .pipeline import load_previous_newsletter
from .rag.index import NewsletterRAG
from .rag.query_gen import QueryGenerator
from .transcript import (
    extract_transcript,
    get_available_dates,
    get_stats_for_date,
    load_source_dataframe,
)

if TYPE_CHECKING:
    from .media_extractor import MediaFile

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DryRunPlan:
    """Summary of what would be processed during a dry run."""

    slug: str
    name: str
    is_virtual: bool
    export_count: int
    available_dates: list[date]
    target_dates: list[date]
    merges: list[str] | None = None


class UnifiedProcessor:
    """Unified processor for both real and virtual groups."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.generator = NewsletterGenerator(config)

    def process_all(self, days: int | None = None) -> dict[str, list[Path]]:
        """Process everything (real + virtual groups)."""

        sources_to_process, _, _ = self._collect_sources()

        results = {}
        for slug, source in sources_to_process.items():
            logger.info(f"\n{'📺' if source.is_virtual else '📝'} Processing: {source.name}")

            if source.is_virtual:
                self._log_merge_stats(source)

            newsletters = self._process_source(source, days)
            results[slug] = newsletters

        return results

    def plan_runs(self, days: int | None = None) -> list[DryRunPlan]:
        """Return a preview of what would be processed."""

        sources_to_process, _, _ = self._collect_sources()

        plans: list[DryRunPlan] = []
        for slug, source in sources_to_process.items():
            available_dates = list(get_available_dates(source))
            target_dates = (
                list(available_dates[-days:])
                if days and available_dates
                else list(available_dates)
            )

            plans.append(
                DryRunPlan(
                    slug=slug,
                    name=source.name,
                    is_virtual=source.is_virtual,
                    export_count=len(source.exports),
                    available_dates=available_dates,
                    target_dates=target_dates,
                    merges=(
                        list(source.merge_config.source_groups)
                        if source.is_virtual and source.merge_config
                        else None
                    ),
                )
            )

        return sorted(plans, key=lambda plan: plan.slug)

    def _collect_sources(
        self,
    ) -> tuple[dict[str, GroupSource], dict, dict[str, GroupSource]]:
        """Discover and prepare sources for processing."""

        logger.info(f"🔍 Scanning {self.config.zips_dir}...")
        real_groups = discover_groups(self.config.zips_dir)

        logger.info(f"📦 Found {len(real_groups)} real group(s):")
        for slug, exports in real_groups.items():
            logger.info(f"  • {exports[0].group_name} ({slug}): {len(exports)} exports")

        virtual_groups = create_virtual_groups(real_groups, self.config.merges)

        if virtual_groups:
            logger.info(f"🔀 Created {len(virtual_groups)} virtual group(s):")
            for slug, source in virtual_groups.items():
                logger.info(
                    f"  • {source.name} ({slug}): merges {len(source.exports)} exports"
                )

        real_sources = {
            slug: GroupSource(
                slug=slug,
                name=exports[0].group_name,
                exports=exports,
                is_virtual=False,
            )
            for slug, exports in real_groups.items()
        }

        all_sources = {**real_sources, **virtual_groups}
        sources_to_process = self._filter_sources(all_sources)

        return sources_to_process, real_groups, virtual_groups

    def _log_merge_stats(self, source: GroupSource):
        """Log merge statistics."""

        try:
            df = load_source_dataframe(source)
        except ValueError as exc:
            logger.warning("  Unable to load virtual group %s: %s", source.slug, exc)
            return
        if df.is_empty():
            logger.info("  Merging 0 groups: no messages available")
            return

        stats = get_merge_stats(df)

        logger.info("  Merging %d groups:", stats.height)
        for row in stats.iter_rows(named=True):
            logger.info(
                "    • %s: %d messages", row["group_name"], row["message_count"]
            )

    def _filter_sources(
        self, all_sources: dict[str, GroupSource]
    ) -> dict[str, GroupSource]:
        """Filter sources to process."""

        if not self.config.skip_real_if_in_virtual:
            return all_sources

        groups_in_merges = set()
        for merge_config in self.config.merges.values():
            groups_in_merges.update(merge_config.source_groups)

        filtered = {}
        for slug, source in all_sources.items():
            if source.is_virtual or slug not in groups_in_merges:
                filtered[slug] = source
            else:
                logger.info(f"  ⏭️  Skipping {source.name} (part of virtual group)")

        return filtered

    def _process_source(self, source: GroupSource, days: int | None) -> list[Path]:
        """Process a single source."""

        from .media_extractor import MediaExtractor

        output_dir = self.config.newsletters_dir / source.slug
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get available dates
        available_dates = list(get_available_dates(source))

        if not available_dates:
            logger.warning(f"  No messages found")
            return []

        target_dates = available_dates[-days:] if days else available_dates
        target_date_set = set(target_dates)

        results = []
        extractor = MediaExtractor(self.config.media_dir)

        media_by_date: dict[date, dict[str, "MediaFile"]] = {}
        for export in source.exports:
            if export.export_date not in target_date_set:
                continue

            media_files = extractor.extract_media_from_zip(
                export.zip_path, export.export_date
            )
            date_media = media_by_date.setdefault(export.export_date, {})

            for filename, media_file in media_files.items():
                if filename in date_media:
                    logger.warning(
                        "    Duplicate media filename %s for %s; keeping first occurrence",
                        filename,
                        export.export_date,
                    )
                    continue

                date_media[filename] = media_file

        for target_date in target_dates:
            logger.info(f"  Processing {target_date}...")

            all_media = media_by_date.get(target_date, {})
            transcript = extract_transcript(source, target_date)

            if not transcript:
                logger.warning(f"    Empty transcript")
                continue

            transcript = MediaExtractor.replace_media_references(transcript, all_media)
            stats = get_stats_for_date(source, target_date)
            if not stats:
                logger.warning("    Unable to compute statistics for %s", target_date)
                continue

            logger.info(
                "    %d messages from %d participants",
                stats["message_count"],
                stats["participant_count"],
            )

            _, previous_newsletter = load_previous_newsletter(output_dir, target_date)

            # Enrichment
            enrichment_section = None
            if self.config.enrichment.enabled:
                cache_manager = CacheManager(self.config.cache.cache_dir)
                enricher = ContentEnricher(self.config.enrichment, cache_manager=cache_manager)
                enrichment_result = asyncio.run(enricher.enrich([(target_date, transcript)], client=self.generator.client))
                enrichment_section = enrichment_result.format_for_prompt(
                    self.config.enrichment.relevance_threshold
                )

            # RAG
            rag_context = None
            if self.config.rag.enabled:
                rag = NewsletterRAG(newsletters_dir=output_dir, config=self.config.rag)
                query_gen = QueryGenerator(self.config.rag)
                query = query_gen.generate(transcript)
                search_results = rag.search(query.search_query)
                if search_results:
                    rag_context = "\n\n".join(
                        f"<<<CONTEXTO_{i}>>>\n{node.get_text()}"
                        for i, node in enumerate(search_results, 1)
                    )

            context = NewsletterContext(
                group_name=source.name,
                transcript=transcript,
                target_date=target_date,
                previous_newsletter=previous_newsletter,
                enrichment_section=enrichment_section,
                rag_context=rag_context,
            )
            newsletter = self.generator.generate(source, context)

            output_path = output_dir / f"{target_date}.md"
            output_path.write_text(newsletter, encoding="utf-8")

            results.append(output_path)
            try:
                logger.info(f"    ✅ {output_path.relative_to(Path.cwd())}")
            except ValueError:
                logger.info(f"    ✅ {output_path}")

        return results

    def list_groups(self) -> dict[str, dict]:
        """List discovered groups."""

        real_groups = discover_groups(self.config.zips_dir)
        virtual_groups = create_virtual_groups(real_groups, self.config.merges)

        all_info = {}

        for slug, exports in real_groups.items():
            dates = [e.export_date for e in exports]
            all_info[slug] = {
                "name": exports[0].group_name,
                "type": "real",
                "export_count": len(exports),
                "date_range": (min(dates), max(dates)),
                "in_virtual": [
                    s
                    for s, c in self.config.merges.items()
                    if slug in c.source_groups
                ],
            }

        for slug, source in virtual_groups.items():
            dates = [e.export_date for e in source.exports]
            all_info[slug] = {
                "name": source.name,
                "type": "virtual",
                "merges": source.merge_config.source_groups,
                "export_count": len(source.exports),
                "date_range": (min(dates), max(dates)),
            }

        return all_info