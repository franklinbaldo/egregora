"""Unified processor with Polars-based message manipulation."""

from dataclasses import dataclass
from pathlib import Path
from datetime import date
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from .media_extractor import MediaFile

from .group_discovery import discover_groups
from .merger import create_virtual_groups, get_merge_stats
from .transcript import (
    extract_transcript,
    get_available_dates,
    get_stats_for_date,
    load_source_dataframe,
)
from .models import GroupSource
from .config import PipelineConfig

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
                list(available_dates[-days:]) if days and available_dates else list(available_dates)
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

    def _collect_sources(self) -> tuple[dict[str, GroupSource], dict, dict[str, GroupSource]]:
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
                logger.info(f"  • {source.name} ({slug}): merges {len(source.exports)} exports")

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
            logger.info("    • %s: %d messages", row["group_name"], row["message_count"])
    
    def _filter_sources(self, all_sources: dict[str, GroupSource]) -> dict[str, GroupSource]:
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

            media_files = extractor.extract_media_from_zip(export.zip_path, export.export_date)
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

            # 1. Extract media from all exports for this date
            all_media = media_by_date.get(target_date, {})
            
            # 2. Get transcript
            transcript = extract_transcript(source, target_date)
            
            if not transcript:
                logger.warning(f"    Empty transcript")
                continue
            
            # 3. Replace media references
            transcript = MediaExtractor.replace_media_references(transcript, all_media)
            
            # 4. Stats
            stats = get_stats_for_date(source, target_date)
            if not stats:
                logger.warning("    Unable to compute statistics for %s", target_date)
                continue

            logger.info(
                "    %d messages from %d participants",
                stats['message_count'],
                stats['participant_count'],
            )
            
            # 5. Generate newsletter with media-linked transcript
            newsletter = self._generate_newsletter(source, transcript, target_date)
            
            # Save
            output_path = output_dir / f"{target_date}.md"
            output_path.write_text(newsletter, encoding='utf-8')
            
            results.append(output_path)
            logger.info(f"    ✅ {output_path.relative_to(Path.cwd())}")
        
        return results
    
    def _generate_newsletter(
        self,
        source: GroupSource,
        transcript: str,
        target_date: date,
    ) -> str:
        """Generate newsletter using existing pipeline."""
        
        from .pipeline import build_llm_input, build_system_instruction, create_client
        try:
            from google import genai
            from google.genai import types
        except ModuleNotFoundError:
            raise ImportError("google-genai is required but not installed")
        
        # Build LLM input using existing pipeline
        llm_input = build_llm_input(
            group_name=source.name,
            timezone=self.config.timezone,
            transcripts=[(target_date, transcript)],
            previous_newsletter=None,  # TODO: integrate previous newsletter
            enrichment_section=None,  # TODO: integrate enrichment
            rag_context=None,  # TODO: integrate RAG
        )
        
        # Use updated system instruction that knows about group tags
        system_instruction = build_system_instruction(
            has_group_tags=source.is_virtual
        )
        
        # Use model override for virtual groups if specified
        model = (
            source.merge_config.model_override 
            if source.is_virtual and source.merge_config and source.merge_config.model_override
            else self.config.model
        )
        
        # Create LLM client and call
        llm_client = create_client()
        
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=llm_input)],
            ),
        ]

        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=-1),
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
            ],
            system_instruction=system_instruction,
        )

        output_lines: list[str] = []
        for chunk in llm_client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if chunk.text:
                output_lines.append(chunk.text)

        return "".join(output_lines).strip()
    
    def list_groups(self) -> dict[str, dict]:
        """List discovered groups."""
        
        real_groups = discover_groups(self.config.zips_dir)
        virtual_groups = create_virtual_groups(real_groups, self.config.merges)
        
        all_info = {}
        
        # Real groups
        for slug, exports in real_groups.items():
            dates = [e.export_date for e in exports]
            all_info[slug] = {
                'name': exports[0].group_name,
                'type': 'real',
                'export_count': len(exports),
                'date_range': (min(dates), max(dates)),
                'in_virtual': [
                    s for s, c in self.config.merges.items() 
                    if slug in c.source_groups
                ],
            }
        
        # Virtual groups
        for slug, source in virtual_groups.items():
            dates = [e.export_date for e in source.exports]
            all_info[slug] = {
                'name': source.name,
                'type': 'virtual',
                'merges': source.merge_config.source_groups,
                'export_count': len(source.exports),
                'date_range': (min(dates), max(dates)),
            }
        
        return all_info
