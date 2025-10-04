"""Unified processor with pandas-based message manipulation."""

from pathlib import Path
from datetime import date
import logging

from .group_discovery import discover_groups
from .merger import create_virtual_groups, get_merge_stats
from .transcript import extract_transcript, get_stats_for_date, get_available_dates
from .models import GroupSource, WhatsAppExport
from .config import PipelineConfig
from .parser import parse_multiple

logger = logging.getLogger(__name__)


class UnifiedProcessor:
    """Unified processor for both real and virtual groups."""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
    
    def process_all(self, days: int | None = None) -> dict[str, list[Path]]:
        """Process everything (real + virtual groups)."""
        
        # 1. Discovery
        logger.info(f"🔍 Scanning {self.config.zips_dir}...")
        real_groups = discover_groups(self.config.zips_dir)
        
        logger.info(f"📦 Found {len(real_groups)} real group(s):")
        for slug, exports in real_groups.items():
            logger.info(f"  • {exports[0].group_name} ({slug}): {len(exports)} exports")
        
        # 2. Create virtual groups
        virtual_groups = create_virtual_groups(real_groups, self.config.merges)
        
        if virtual_groups:
            logger.info(f"🔀 Created {len(virtual_groups)} virtual group(s):")
            for slug, source in virtual_groups.items():
                logger.info(f"  • {source.name} ({slug}): merges {len(source.exports)} exports")
        
        # 3. Convert real groups to GroupSource
        real_sources = {
            slug: GroupSource(
                slug=slug,
                name=exports[0].group_name,
                exports=exports,
                is_virtual=False,
            )
            for slug, exports in real_groups.items()
        }
        
        # 4. Combine
        all_sources = {**real_sources, **virtual_groups}
        
        # 5. Filter
        sources_to_process = self._filter_sources(all_sources)
        
        # 6. Process
        results = {}
        for slug, source in sources_to_process.items():
            logger.info(f"\n{'📺' if source.is_virtual else '📝'} Processing: {source.name}")
            
            if source.is_virtual:
                self._log_merge_stats(source)
            
            newsletters = self._process_source(source, days)
            results[slug] = newsletters
        
        return results
    
    def _log_merge_stats(self, source: GroupSource):
        """Log merge statistics."""
        
        from .merger import merge_with_tags
        
        df = merge_with_tags(source.exports, source.merge_config)
        stats = get_merge_stats(df)
        
        logger.info(f"  Merging {len(stats)} groups:")
        for _, row in stats.iterrows():
            logger.info(f"    • {row['group_name']}: {row['message_count']} messages")
    
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
        
        output_dir = self.config.newsletters_dir / source.slug
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get available dates
        available_dates = get_available_dates(source)
        
        if not available_dates:
            logger.warning(f"  No messages found")
            return []
        
        target_dates = available_dates[-days:] if days else available_dates
        
        results = []
        
        for target_date in target_dates:
            logger.info(f"  Processing {target_date}...")
            
            # Extract transcript
            transcript = extract_transcript(source, target_date)
            
            if not transcript:
                logger.warning(f"    Empty transcript")
                continue
            
            # Stats
            stats = get_stats_for_date(source, target_date)
            logger.info(f"    {stats['message_count']} messages from {stats['participant_count']} participants")
            
            # Generate newsletter
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