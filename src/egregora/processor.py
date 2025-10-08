"""Unified processor with Polars-based message manipulation."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import polars as pl
import yaml

from .anonymizer import Anonymizer
from .cache_manager import CacheManager
from .config import PipelineConfig
from .enrichment import ContentEnricher
from .generator import PostContext, PostGenerator
from .group_discovery import discover_groups
from .merger import create_virtual_groups, get_merge_stats
from .models import GroupSource
from .pipeline import load_previous_post
from .profiles import ParticipantProfile, ProfileRepository, ProfileUpdater
from .rag.index import PostRAG
from .rag.keyword_utils import build_llm_keyword_provider
from .rag.query_gen import QueryGenerator
from .remote_sync import sync_remote_source_config
from .transcript import (
    get_available_dates,
    load_source_dataframe,
    render_transcript,
)

if TYPE_CHECKING:
    from .media_extractor import MediaFile

logger = logging.getLogger(__name__)


def _build_post_metadata(
    source: "GroupSource", target_date: date, config: PipelineConfig
) -> dict[str, object]:
    """Return front matter metadata compatible with the Material blog plugin."""

    created = datetime.combine(target_date, time.min).replace(
        tzinfo=config.timezone
    )
    categories = ["daily", source.slug]
    tags = [source.name, "whatsapp"]

    return {
        "title": f"📩 {source.name} — Diário de {target_date:%Y-%m-%d}",
        "date": created.isoformat(),
        "lang": config.post_language,
        "authors": [config.default_post_author],
        "categories": categories,
        "tags": tags,
    }


def _ensure_blog_front_matter(
    text: str, *, source: "GroupSource", target_date: date, config: PipelineConfig
) -> str:
    """Prepend YAML front matter when it's missing."""

    stripped = text.lstrip()
    if stripped.startswith("---"):
        return text

    metadata = _build_post_metadata(source, target_date, config)
    front_matter = yaml.safe_dump(
        metadata, sort_keys=False, allow_unicode=True
    ).strip()

    prefix_len = len(text) - len(stripped)
    prefix = text[:prefix_len]
    return f"{prefix}---\n{front_matter}\n---\n\n{stripped}"


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
        self.generator = PostGenerator(config)

        self._profile_updater: ProfileUpdater | None = None
        self._profile_limit_per_run: int = 0

        if self.config.profiles.enabled:
            self._profile_updater = ProfileUpdater(
                min_messages=self.config.profiles.min_messages,
                min_words_per_message=self.config.profiles.min_words_per_message,
                decision_model=self.config.profiles.decision_model,
                rewrite_model=self.config.profiles.rewrite_model,
                max_api_retries=self.config.profiles.max_api_retries,
                minimum_retry_seconds=self.config.profiles.minimum_retry_seconds,
            )
            self._profile_limit_per_run = self.config.profiles.max_profiles_per_run

    def process_all(self, days: int | None = None) -> dict[str, list[Path]]:
        """Process everything (real + virtual groups)."""

        sources_to_process, _, _ = self._collect_sources()

        results = {}
        for slug, source in sources_to_process.items():
            logger.info(f"\n{'📺' if source.is_virtual else '📝'} Processing: {source.name}")

            if source.is_virtual:
                self._log_merge_stats(source)

            posts = self._process_source(source, days)
            results[slug] = posts

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

    def _sync_remote_source(self) -> None:
        """Download WhatsApp exports from the configured remote source."""

        outcome = sync_remote_source_config(self.config, logger=logger)
        if not outcome.attempted:
            return

        if outcome.error:
            logger.warning("  ⚠️ Falha ao sincronizar fonte remota: %s", outcome.error)
            return

        if outcome.new_archives:
            base = self.config.zips_dir.resolve()
            logger.info("  %d arquivo(s) novo(s) sincronizado(s):", len(outcome.new_archives))
            for path in outcome.new_archives:
                try:
                    rel = path.relative_to(base)
                except ValueError:
                    rel = path
                logger.info("    • %s", rel)
        else:
            logger.info("  Nenhum arquivo novo encontrado.")


    def _collect_sources(
        self,
    ) -> tuple[dict[str, GroupSource], dict, dict[str, GroupSource]]:
        """Discover and prepare sources for processing."""

        self._sync_remote_source()

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

    def _write_group_index(
        self,
        source: "GroupSource",
        group_dir: Path,
        post_paths: list[Path],
    ) -> None:
        """Ensure an index page summarising generated posts for *source*."""

        index_path = group_dir / "index.md"
        metadata = {
            "title": f"{source.name} — Sumário",
            "lang": self.config.post_language,
            "authors": [self.config.default_post_author],
            "categories": [source.slug, "summary"],
        }
        front_matter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()

        # Merge existing posts on disk with the ones produced in this run so the
        # index remains cumulative when processing a limited window of days.
        all_posts: set[Path] = set()

        daily_dir = group_dir / "posts" / "daily"
        if daily_dir.exists():
            all_posts.update(
                path
                for path in daily_dir.glob("*.md")
                if path.is_file()
            )

        all_posts.update(post_paths)

        items: list[str] = []
        for path in sorted(all_posts, key=lambda p: p.stem, reverse=True):
            try:
                relative = path.relative_to(group_dir)
            except ValueError:
                relative = path
            items.append(f"- [{path.stem}]({relative.as_posix()})")

        if not items:
            items.append("_Nenhuma edição gerada ainda._")

        body = "\n".join(items)
        content_lines = [
            "---",
            front_matter,
            "---",
            "",
            f"# {source.name}",
            "",
            body,
            "",
        ]
        content = "\n".join(content_lines)

        if index_path.exists():
            existing = index_path.read_text(encoding="utf-8")
            if existing == content:
                return

        index_path.write_text(content, encoding="utf-8")

    def _process_source(self, source: GroupSource, days: int | None) -> list[Path]:
        """Process a single source."""

        from .media_extractor import MediaExtractor

        group_dir = self.config.posts_dir / source.slug
        group_dir.mkdir(parents=True, exist_ok=True)

        posts_base = group_dir / "posts"
        daily_dir = posts_base / "daily"
        daily_dir.mkdir(parents=True, exist_ok=True)

        media_dir = group_dir / "media"
        media_dir.mkdir(parents=True, exist_ok=True)

        profiles_base = group_dir / "profiles"
        profiles_base.mkdir(parents=True, exist_ok=True)

        profile_repository = None
        if self.config.profiles.enabled and self._profile_updater:
            profile_repository = ProfileRepository(
                data_dir=profiles_base / "json",
                docs_dir=profiles_base,
            )

        try:
            full_df = load_source_dataframe(source)
        except ValueError as exc:
            logger.warning("  Unable to load messages for %s: %s", source.slug, exc)
            return []

        if full_df.is_empty():
            logger.warning(f"  No messages found")
            return []

        available_dates = sorted({d for d in full_df.get_column("date").to_list()})
        target_dates = available_dates[-days:] if days else available_dates

        results = []
        extractor = MediaExtractor(group_dir, group_slug=source.slug)

        exports_by_date: dict[date, list] = {}
        for export in source.exports:
            exports_by_date.setdefault(export.export_date, []).append(export)

        for target_date in target_dates:
            logger.info(f"  Processing {target_date}...")

            df_day = full_df.filter(pl.col("date") == target_date).sort("timestamp")

            if df_day.is_empty():
                logger.warning("    Empty transcript")
                continue

            attachment_names = MediaExtractor.find_attachment_names_dataframe(df_day)
            all_media: dict[str, "MediaFile"] = {}
            if attachment_names:
                remaining = set(attachment_names)
                for export in exports_by_date.get(target_date, []):
                    extracted = extractor.extract_specific_media_from_zip(
                        export.zip_path,
                        target_date,
                        remaining,
                    )
                    if extracted:
                        all_media.update(extracted)
                        remaining.difference_update(extracted.keys())
                    if not remaining:
                        break

            public_paths = MediaExtractor.build_public_paths(
                all_media,
                url_prefix=self.config.media_url_prefix,
                relative_to=(daily_dir if self.config.media_url_prefix is None else None),
            )

            df_render = MediaExtractor.replace_media_references_dataframe(
                df_day,
                all_media,
                public_paths=public_paths,
            )
            transcript = render_transcript(df_render, use_tagged=source.is_virtual)

            stats = {
                "message_count": df_day.height,
                "participant_count": df_day.get_column("author").n_unique(),
                "first_message": df_day.get_column("timestamp").min(),
                "last_message": df_day.get_column("timestamp").max(),
            }

            logger.info(
                "    %d messages from %d participants",
                stats["message_count"],
                stats["participant_count"],
            )

            _, previous_post = load_previous_post(daily_dir, target_date)

            # Enrichment
            enrichment_section = None
            if self.config.enrichment.enabled:
                cache_manager = None
                if self.config.cache.enabled:
                    cache_manager = CacheManager(
                        self.config.cache.cache_dir,
                        size_limit_mb=self.config.cache.max_disk_mb,
                    )
                    if self.config.cache.auto_cleanup_days:
                        cache_manager.cleanup_old_entries(
                            self.config.cache.auto_cleanup_days
                        )
                enricher = ContentEnricher(
                    self.config.enrichment,
                    cache_manager=cache_manager,
                )
                enrichment_result = asyncio.run(
                    enricher.enrich_dataframe(
                        df_day,
                        client=self.generator.client,
                        target_dates=[target_date],
                    )
                )
                enrichment_section = enrichment_result.format_for_prompt(
                    self.config.enrichment.relevance_threshold
                )
                metrics = enrichment_result.metrics
                if metrics:
                    domains = ", ".join(metrics.domains) if metrics.domains else "-"
                    logger.info(
                        "    [Enriquecimento] %d/%d itens relevantes (≥%d) em %.2fs; domínios=%s; erros=%d",
                        metrics.relevant_items,
                        metrics.analyzed_items,
                        metrics.threshold,
                        metrics.duration_seconds,
                        domains,
                        metrics.error_count,
                    )

            # RAG
            rag_context = None
            if self.config.rag.enabled:
                keyword_provider = None
                try:
                    keyword_provider = build_llm_keyword_provider(
                        self.generator.client,
                        model=self.config.model,
                    )
                except Exception as exc:  # pragma: no cover - optional dependency
                    logger.warning(
                        "    [RAG] Falha ao inicializar extrator de palavras-chave: %s",
                        exc,
                    )

                if keyword_provider is not None:
                    rag = PostRAG(
                        posts_dir=self.config.posts_dir,
                        config=self.config.rag,
                    )
                    query_gen = QueryGenerator(
                        self.config.rag,
                        keyword_provider=keyword_provider,
                    )
                    query = query_gen.generate(transcript)
                    search_results = rag.search(query.search_query)
                    if search_results:
                        rag_context = "\n\n".join(
                            f"<<<CONTEXTO_{i}>>>\n{node.get_text()}"
                            for i, node in enumerate(search_results, 1)
                        )

            context = PostContext(
                group_name=source.name,
                transcript=transcript,
                target_date=target_date,
                previous_post=previous_post,
                enrichment_section=enrichment_section,
                rag_context=rag_context,
            )
            post = self.generator.generate(source, context)

            media_section = MediaExtractor.format_media_section(
                all_media,
                public_paths=public_paths,
            )
            if media_section:
                post = (
                    f"{post.rstrip()}\n\n## Mídias Compartilhadas\n{media_section}\n"
                )

            post = _ensure_blog_front_matter(
                post, source=source, target_date=target_date, config=self.config
            )

            output_path = daily_dir / f"{target_date}.md"
            output_path.write_text(post, encoding="utf-8")

            if profile_repository and self._profile_updater:
                try:
                    self._update_profiles_for_day(
                        repository=profile_repository,
                        source=source,
                        target_date=target_date,
                        post_text=post,
                    )
                except Exception as exc:
                    logger.warning(
                        "    ⚠️ Falha ao atualizar perfis para %s: %s",
                        target_date,
                        exc,
                    )

            results.append(output_path)
            try:
                logger.info(f"    ✅ {output_path.relative_to(Path.cwd())}")
            except ValueError:
                logger.info(f"    ✅ {output_path}")

        self._write_group_index(source, group_dir, results)
        return results

    def _update_profiles_for_day(
        self,
        *,
        repository: ProfileRepository,
        source: GroupSource,
        target_date: date,
        post_text: str,
    ) -> None:
        updater = self._profile_updater
        if updater is None:
            return

        try:
            df = load_source_dataframe(source)
        except Exception as exc:
            logger.debug("    Unable to load dataframe for profiles: %s", exc)
            return

        df_day = df.filter(pl.col("date") == target_date)
        if df_day.is_empty():
            return

        df_day = df_day.sort("timestamp")
        conversation = self._build_profile_conversation(df_day)
        if not conversation.strip():
            return

        client = self._get_profiles_client()
        if client is None:
            return

        context_block = self._format_profile_context(target_date, conversation, post_text)
        updates_made = False

        authors_series = df_day.get_column("author")
        unique_authors = {
            str(author).strip()
            for author in authors_series.to_list()
            if isinstance(author, str) and author.strip()
        }

        processed = 0
        quota_exhausted = False

        for raw_author in sorted(unique_authors):
            if quota_exhausted:
                break
            if self._profile_limit_per_run and processed >= self._profile_limit_per_run:
                logger.info(
                    "    ⏸️  Limite diário de perfis atingido (%d)",
                    self._profile_limit_per_run,
                )
                break

            member_uuid = Anonymizer.anonymize_author(raw_author, format="full")
            member_label = Anonymizer.anonymize_author(raw_author, format="human")
            current_profile = repository.load(member_uuid)

            should_consider, _ = updater.should_update_profile_dataframe(
                raw_author,
                current_profile,
                df_day,
            )
            if not should_consider:
                continue

            try:
                should_update, reasoning, highlights, insights = asyncio.run(
                    updater.should_update_profile(
                        member_id=member_label,
                        current_profile=current_profile,
                        full_conversation=conversation,
                        gemini_client=client,
                    )
                )
            except RuntimeError as exc:
                if "RESOURCE_EXHAUSTED" in str(exc):
                    logger.warning(
                        "    ⚠️ Limite diário do Gemini atingido ao decidir perfil de %s; interrompendo atualizações.",
                        member_label,
                    )
                    quota_exhausted = True
                    break
                logger.warning(
                    "    ⚠️ Erro ao decidir atualização de perfil de %s: %s",
                    member_label,
                    exc,
                )
                continue

            if not should_update:
                logger.debug("    Perfil de %s sem alterações (%s)", member_label, reasoning)
                continue

            try:
                profile = asyncio.run(
                    self._async_update_profile(
                        updater=updater,
                        member_label=member_label,
                        current_profile=current_profile,
                        highlights=highlights,
                        insights=insights,
                        conversation=conversation,
                        context_block=context_block,
                        client=client,
                    )
                )
            except RuntimeError as exc:
                if "RESOURCE_EXHAUSTED" in str(exc):
                    logger.warning(
                        "    ⚠️ Limite diário do Gemini atingido ao reescrever perfil de %s; interrompendo atualizações.",
                        member_label,
                    )
                    quota_exhausted = True
                    break
                logger.warning(
                    "    ⚠️ Erro ao atualizar perfil de %s: %s",
                    member_label,
                    exc,
                )
                continue

            repository.save(member_uuid, profile)
            updates_made = True
            processed += 1
            logger.info(
                "    👤 Perfil atualizado: %s (versão %d)",
                member_label,
                profile.analysis_version,
            )

        if updates_made:
            repository.write_index()

    async def _async_update_profile(
        self,
        *,
        updater: ProfileUpdater,
        member_label: str,
        current_profile,
        highlights,
        insights,
        conversation: str,
        context_block: str,
        client,
    ) -> Optional[ParticipantProfile]:
        profile = await updater.rewrite_profile(
            member_id=member_label,
            old_profile=current_profile,
            recent_conversations=[context_block],
            participation_highlights=highlights,
            interaction_insights=insights,
            gemini_client=client,
        )
        return profile

    def _build_profile_conversation(self, df_day: pl.DataFrame) -> str:
        lines: list[str] = []
        for row in df_day.iter_rows(named=True):
            timestamp = row.get("timestamp")
            if hasattr(timestamp, "strftime"):
                time_str = timestamp.strftime("%H:%M")
            else:
                time_str = "??:??"
            author = str(row.get("author") or "").strip()
            message = str(row.get("message") or "").strip()
            if not author:
                continue
            member_label = Anonymizer.anonymize_author(author, format="human")
            lines.append(f"{time_str} - {member_label}: {message}")
        return "\n".join(lines)

    def _format_profile_context(
        self,
        target_date: date,
        conversation: str,
        post_text: str,
    ) -> str:
        blocks = [f"### {target_date.isoformat()}\n{conversation.strip()}".strip()]
        if post_text.strip():
            blocks.append(
                "### Post do dia\n" + post_text.strip()
            )
        return "\n\n".join(blocks)

    def _get_profiles_client(self):
        if self._profile_updater is None:
            return None
        try:
            return self.generator.client
        except RuntimeError as exc:
            logger.warning("    ⚠️ Perfis desativados: %s", exc)
            return None

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
