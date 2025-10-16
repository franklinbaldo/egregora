"Unified processor with Polars-based message manipulation."

from __future__ import annotations

import asyncio
import logging
import re
import textwrap
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

import polars as pl
import yaml
from diskcache import Cache

from .anonymizer import Anonymizer
from .config import PipelineConfig
from .enrichment import ContentEnricher
from .gemini_manager import GeminiManager
from .generator import PostContext, PostGenerator
from .markdown_utils import format_markdown

# from .group_discovery import discover_groups
from .media_extractor import MediaExtractor, MediaFile
from .merger import create_virtual_groups, get_merge_stats
from .models import GroupSource, WhatsAppExport
from .privacy import PrivacyViolationError, validate_newsletter_privacy
from .profiles import ParticipantProfile, ProfileRepository, ProfileUpdater
from .rag.chromadb_rag import ChromadbRAG
from .rag.keyword_utils import build_llm_keyword_provider
from .rag.query_gen import QueryGenerator
from .transcript import (
    get_available_dates,
    load_source_dataframe,
    render_transcript,
)
from .types import GroupSlug

try:  # pragma: no cover - optional dependency
    from google.genai import errors as genai_errors
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    genai_errors = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from .enrichment import EnrichmentResult

logger = logging.getLogger(__name__)

YAML_DELIMITER = "---"
QUOTA_WARNING_THRESHOLD = 15
MIN_YAML_PARTS = 3
_TRANSIENT_STATUS_CODES = {500, 502, 503, 504}
MAX_MEDIA_CAPTION_LENGTH = 160


def _is_transient_gemini_error(exc: Exception) -> bool:
    """Return ``True`` when *exc* looks like a temporary Gemini outage."""

    message = str(exc)
    if "UNAVAILABLE" in message or "model is overloaded" in message:
        return True

    if genai_errors is not None and isinstance(exc, genai_errors.ServerError):
        status_code = getattr(exc, "status_code", None)
        if status_code in _TRANSIENT_STATUS_CODES:
            return True

    return False


def _create_cache(directory: Path, size_limit_mb: int | None) -> Cache:
    directory.mkdir(parents=True, exist_ok=True)
    size_limit_bytes = 0 if size_limit_mb is None else max(0, int(size_limit_mb)) * 1024 * 1024
    return Cache(directory=str(directory), size_limit=size_limit_bytes)


def _coerce_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    return None


def _cleanup_cache(cache: Cache, days: int) -> int:
    threshold = datetime.now(UTC) - timedelta(days=max(0, int(days)))
    removed = 0

    for key in list(cache.iterkeys()):
        entry = cache.get(key)
        if not isinstance(entry, dict):
            cache.delete(key)
            continue

        last_used = _coerce_timestamp(entry.get("last_used"))
        if last_used is None:
            continue

        if last_used < threshold:
            cache.delete(key)
            removed += 1
            continue

        if not isinstance(entry.get("last_used"), datetime):
            entry["last_used"] = last_used
            cache.set(key, entry)

    return removed


def _build_post_metadata(
    source: GroupSource, target_date: date, config: PipelineConfig
) -> dict[str, object]:
    """Return front matter metadata compatible with the Material blog plugin."""

    created = datetime.combine(target_date, time.min).replace(tzinfo=config.timezone)
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

#TODO: This function has some complex logic for handling front matter. It could be simplified and made more robust.
def _ensure_blog_front_matter(
    text: str, *, source: GroupSource, target_date: date, config: PipelineConfig
) -> str:
    """Merge Gemini-generated frontmatter with programmatic metadata."""

    stripped = text.lstrip()

    # Check if content has frontmatter (including wrapped in code blocks)
    if stripped.startswith("```\n---") or stripped.startswith("---"):
        yaml_content = ""
        remaining_content = stripped

        # Handle normal frontmatter first
        if stripped.startswith(YAML_DELIMITER):
            parts = stripped.split(YAML_DELIMITER, 2)
            if len(parts) >= MIN_YAML_PARTS:
                yaml_content = parts[1]
                remaining_content = parts[2].lstrip()

        # Remove any wrapped frontmatter blocks from remaining content
        while f"```\n{YAML_DELIMITER}" in remaining_content or f"```yaml\n{YAML_DELIMITER}" in remaining_content:
            # Check for both plain and yaml-labeled code blocks
            patterns = [f"```\n{YAML_DELIMITER}", f"```yaml\n{YAML_DELIMITER}"]
            for pattern in patterns:
                if pattern in remaining_content:
                    start_idx = remaining_content.find(pattern)
                    # Look for closing pattern
                    end_pattern = f"{YAML_DELIMITER}\n```"
                    end_idx = remaining_content.find(end_pattern, start_idx)
                    if end_idx > start_idx:
                        # Remove the entire wrapped block
                        remaining_content = (
                            remaining_content[:start_idx]
                            + remaining_content[end_idx + len(end_pattern):]
                        ).strip()
                        break  # Process one at a time
            else:
                break  # No more patterns found

        # Parse existing YAML and merge with programmatic metadata
        try:
            existing_metadata = yaml.safe_load(yaml_content) or {}
        except yaml.YAMLError:
            existing_metadata = {}

        # Get programmatic metadata and merge
        programmatic_metadata = _build_post_metadata(source, target_date, config)
        merged_metadata = {**programmatic_metadata, **existing_metadata}

        # Generate clean frontmatter
        front_matter = yaml.safe_dump(merged_metadata, sort_keys=False, allow_unicode=True).strip()
        return f"{YAML_DELIMITER}\n{front_matter}\n{YAML_DELIMITER}\n\n{remaining_content}"

    # No frontmatter found, add programmatic one
    metadata = _build_post_metadata(source, target_date, config)
    front_matter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()
    prefix_len = len(text) - len(stripped)
    prefix = text[:prefix_len]
    return f"{prefix}{YAML_DELIMITER}\n{front_matter}\n{YAML_DELIMITER}\n\n{stripped}"


def _add_member_profile_links(
    text: str,
    *,
    config: PipelineConfig,
    source: GroupSource,
    repository: ProfileRepository | None = None,
) -> str:
    """Convert anonymized UUID mentions to profile emoji links."""

    if not config.profiles.link_members_in_posts:
        return text

    # FIXME: The regex could be improved to be more specific and avoid false positives.
    uuid_pattern = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    
    markdown_with_uuid = re.compile(
        rf"(?P<link>\[[^\]]+\]\([^)]+\))\s*(?P<uuid>{uuid_pattern})",
        re.IGNORECASE,
    )
    # Match UUIDs in parentheses that are NOT in media section or file paths
    paren_uuid = re.compile(rf"\((?P<uuid>{uuid_pattern})\)", re.IGNORECASE)
    # Match bare UUIDs that are NOT followed by file extensions
    bare_uuid = re.compile(rf"(?<![\w-])(?P<uuid>{uuid_pattern})(?![\w-])", re.IGNORECASE)

    workspace_root = Path.cwd().parent if Path.cwd().name == "egregora" else Path.cwd() #TODO: THIS IS A HACKY AND BAD UX, THE USER MUST GIVE THE OUTPUT PATH WE SHOULD NOT GUESS IT
    site_profiles_dir = workspace_root / "egregora-site" / source.slug / "profiles"

    profile_files: dict[str, Path] = {}
    if repository is not None:
        try:
            docs_dir = repository.docs_dir
            for identifier, _profile in repository.iter_profiles():
                candidate = docs_dir / f"{identifier}.md"
                if candidate.exists():
                    profile_files[identifier.lower()] = candidate
        except Exception:
            pass

    if site_profiles_dir.exists():
        for profile_file in site_profiles_dir.glob("*.md"):
            if profile_file.name.lower() == "index.md":
                continue
            profile_files[profile_file.stem.lower()] = profile_file

    def _resolve_profile(uuid_value: str) -> str | None:
        identifier = uuid_value.lower()
        candidate_path = profile_files.get(identifier)
        if candidate_path is not None and candidate_path.exists():
            rel = PurePosixPath("../../profiles") / candidate_path.name
            return rel.as_posix()

        base = (config.profiles.profile_base_url or "").strip()
        if base:
            base_clean = base.rstrip("/") or "/"
            rel = PurePosixPath(f"{base_clean}/{identifier}")
            return rel.as_posix()

        return None

    def _format_link(resolved: str) -> str:
        return f"[🪪]({resolved})"

    def _replace_markdown(match: re.Match[str]) -> str:
        resolved = _resolve_profile(match.group("uuid"))
        link = match.group("link")
        emoji = _format_link(resolved) if resolved else "🪪"
        return f"{link} {emoji}"

    def _replace_paren(match: re.Match[str]) -> str:
        # Skip if this appears to be in a media section
        uuid_str = match.group("uuid")
        full_match = match.group(0)
        start_pos = match.start()
        
        # Check if we're in a media section (rough heuristic)
        before_context = text[max(0, start_pos-100):start_pos]
        if "## Mídias Compartilhadas" in before_context or "../media/" in before_context:
            return full_match  # Don't convert media UUIDs
            
        resolved = _resolve_profile(uuid_str)
        emoji = _format_link(resolved) if resolved else "🪪"
        return emoji

    def _replace_bare(match: re.Match[str]) -> str:
        # Skip if this appears to be in a media section
        uuid_str = match.group("uuid")
        full_match = match.group(0)
        start_pos = match.start()
        
        # Check if we're in a media section
        before_context = text[max(0, start_pos-100):start_pos]
        if "## Mídias Compartilhadas" in before_context or "../media/" in before_context:
            return full_match  # Don't convert media UUIDs
            
        resolved = _resolve_profile(uuid_str)
        return _format_link(resolved) if resolved else "🪪"

    text = markdown_with_uuid.sub(_replace_markdown, text)
    text = paren_uuid.sub(_replace_paren, text)
    text = bare_uuid.sub(_replace_bare, text)
    return text


def _apply_media_captions_from_enrichment(
    media_map: dict[str, MediaFile],
    enrichment_result: EnrichmentResult | None,
) -> None:
    """Populate media captions based on enrichment summaries."""

    if not media_map or enrichment_result is None:
        return

    for item in enrichment_result.items:
        reference = item.reference
        media_key = getattr(reference, "media_key", None)
        if not media_key:
            continue

        media = media_map.get(media_key)
        if media is None or item.analysis is None:
            continue

        caption = item.analysis.summary or ""
        if not caption and item.analysis.topics:
            caption = item.analysis.topics[0]
        caption = caption.strip()
        if not caption:
            continue

        normalized = " ".join(caption.split())
        if len(normalized) > MAX_MEDIA_CAPTION_LENGTH:
            normalized = textwrap.shorten(
                normalized, width=MAX_MEDIA_CAPTION_LENGTH, placeholder="…"
            )
        media.caption = normalized


def _load_previous_post(
    posts_dir: Path,
    reference_date: date,
    *,
    search_window_days: int = 7,
) -> tuple[Path, str | None]:
    """Return the most recent post prior to ``reference_date``."""
    if search_window_days < 1:
        raise ValueError("search_window_days must be at least 1 day")

    target_path = posts_dir / f"{(reference_date - timedelta(days=1)).isoformat()}.md"

    for delta in range(1, search_window_days + 1):
        candidate_date = reference_date - timedelta(days=delta)
        candidate_path = posts_dir / f"{candidate_date.isoformat()}.md"
        if candidate_path.exists():
            return candidate_path, candidate_path.read_text(encoding="utf-8")

    return target_path, None


def _filter_target_dates(
    available_dates: list[date],
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    days: int | None = None,
) -> list[date]:
    """Filter available dates based on the provided criteria."""
    # Date range has priority
    if from_date or to_date:
        filtered_dates = available_dates
        if from_date:
            filtered_dates = [d for d in filtered_dates if d >= from_date]
        if to_date:
            filtered_dates = [d for d in filtered_dates if d <= to_date]
        return filtered_dates

    if days:
        return available_dates[-days:]

    return available_dates


@dataclass(slots=True)
class DryRunPlan:
    """Summary of what would be processed during a dry run."""

    slug: GroupSlug
    name: str
    is_virtual: bool
    export_count: int
    available_dates: list[date]
    target_dates: list[date]
    merges: list[GroupSlug] | None = None


class UnifiedProcessor:
    """Unified processor for both real and virtual groups."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self._gemini_manager: GeminiManager | None = None
        self._generator: PostGenerator | None = None

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

    @property
    def gemini_manager(self) -> GeminiManager:
        """Lazily instantiate the optional Gemini manager."""

        if self._gemini_manager is None:
            self._gemini_manager = GeminiManager(
                retry_attempts=3,
                minimum_retry_seconds=30.0,
            )
        return self._gemini_manager

    @property
    def generator(self) -> PostGenerator:
        """Lazily instantiate the post generator to defer Gemini requirements."""

        if self._generator is None:
            # Only provide gemini_manager when enrichment is enabled
            gemini_manager = self.gemini_manager if self.config.enrichment.enabled else None
            self._generator = PostGenerator(self.config, gemini_manager=gemini_manager)
        return self._generator

    #TODO: The estimation is very rough and could be improved.
    def estimate_api_usage(
        self,
        *,
        days: int | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict[str, Any]:
        """Estimate API quota usage for the planned processing."""
        sources_to_process, _, _ = self._collect_sources()

        total_posts = 0
        total_enrichment_calls = 0
        group_estimates = {}

        for slug, source in sources_to_process.items():
            available_dates = list(get_available_dates(source))
            target_dates = _filter_target_dates(
                available_dates,
                from_date=from_date,
                to_date=to_date,
                days=days,
            )

            group_posts = len(target_dates)
            total_posts += group_posts

            # Estimate enrichment calls (rough estimate)
            enrichment_calls = 0
            if self.config.enrichment.enabled:
                # Rough estimate: 1-3 enrichment calls per day on average
                enrichment_calls = group_posts * 2  # Conservative estimate

            total_enrichment_calls += enrichment_calls

            group_estimates[slug] = {
                "posts": group_posts,
                "enrichment_calls": enrichment_calls,
                "date_range": (target_dates[0], target_dates[-1]) if target_dates else None,
            }

        # Free tier limits (based on the issue description)
        free_tier_limit = 15  # requests per minute
        estimated_minutes = (total_posts + total_enrichment_calls) / free_tier_limit

        return {
            "total_api_calls": total_posts + total_enrichment_calls,
            "post_generation_calls": total_posts,
            "enrichment_calls": total_enrichment_calls,
            "estimated_time_minutes": estimated_minutes,
            "free_tier_minutes_needed": estimated_minutes,
            "groups": group_estimates,
            "warning": (
                "⚠️ Esta operação pode exceder a quota gratuita do Gemini"
                if total_posts + total_enrichment_calls > QUOTA_WARNING_THRESHOLD
                else None
            ),
        }

    def process_all(
        self,
        *,
        days: int | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict[GroupSlug, list[Path]]:
        """Process everything (real + virtual groups)."""

        sources_to_process, _, _ = self._collect_sources()

        results: dict[GroupSlug, list[Path]] = {}
        for slug, source in sources_to_process.items():
            logger.info(f"\n{'📺' if source.is_virtual else '📝'} Processing: {source.name}")

            if source.is_virtual:
                self._log_merge_stats(source)

            posts = self._process_source(
                source,
                days=days,
                from_date=from_date,
                to_date=to_date,
            )
            results[slug] = posts

        return results

    def plan_runs(
        self,
        *,
        days: int | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[DryRunPlan]:
        """Return a preview of what would be processed."""

        sources_to_process, _, _ = self._collect_sources()

        plans: list[DryRunPlan] = []
        for slug, source in sources_to_process.items():
            available_dates = list(get_available_dates(source))
            target_dates = _filter_target_dates(
                available_dates,
                from_date=from_date,
                to_date=to_date,
                days=days,
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

    #TODO: This function uses a list of hardcoded patterns to extract the group name. This could be made more configurable.
    def _extract_group_name_from_chat_file(self, chat_filename: str) -> str:
        """Extract group name from WhatsApp chat filename."""
        # Pattern: "Conversa do WhatsApp com GROUP_NAME.txt"

        # Remove file extension
        base_name = chat_filename.replace(".txt", "")

        # Common patterns in WhatsApp exports
        patterns = [
            r"Conversa do WhatsApp com (.+)",  # Portuguese
            r"WhatsApp Chat with (.+)",  # English
            r"Chat de WhatsApp con (.+)",  # Spanish
        ]

        for pattern in patterns:
            match = re.search(pattern, base_name, re.IGNORECASE)
            if match:
                group_name = match.group(1).strip()
                # Remove common suffixes like dates, emojis at the end
                group_name = re.sub(r"\s*[🀀-🟿]+\s*$", "", group_name).strip()
                return group_name

        # Fallback: use the whole filename without extension
        return base_name

    #TODO: This function generates a slug from the group name. It could be improved to handle more edge cases.
    def _generate_group_slug(self, group_name: str) -> str:
        """Generate a URL-friendly slug from group name."""

        # Normalize unicode characters
        slug = unicodedata.normalize("NFKD", group_name)
        slug = slug.encode("ascii", "ignore").decode("ascii")

        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r"[^\w\s-]", "", slug.lower())
        slug = re.sub(r"[-\s]+", "-", slug)

        # Remove leading/trailing hyphens
        slug = slug.strip("-")

        return slug or "whatsapp-group"

    def _collect_sources(
        self,
    ) -> tuple[
        dict[GroupSlug, GroupSource],
        dict[GroupSlug, list[WhatsAppExport]],
        dict[GroupSlug, GroupSource],
    ]:
        """Process the specified ZIP files."""

        if not self.config.zip_files:
            raise ValueError("No ZIP files specified. Use the zip_files parameter.")

        real_groups = self._process_zip_files()
        virtual_groups = self._create_virtual_groups(real_groups)

        real_sources: dict[GroupSlug, GroupSource] = {
            slug: GroupSource(
                slug=slug,
                name=exports[0].group_name,
                exports=exports,
                is_virtual=False,
            )
            for slug, exports in real_groups.items()
        }

        all_sources: dict[GroupSlug, GroupSource] = {
            **real_sources,
            **virtual_groups,
        }
        sources_to_process = self._filter_sources(all_sources)

        return sources_to_process, real_groups, virtual_groups

    def _process_zip_files(self) -> dict[GroupSlug, list[WhatsAppExport]]:
        """Process the specified ZIP files."""
        num_files = len(self.config.zip_files)
        if num_files == 1:
            logger.info(f"🔍 Processing ZIP file: {self.config.zip_files[0]}")
        else:
            logger.info(f"🔍 Processing {num_files} ZIP files for merging:")

        real_groups: dict[GroupSlug, list[WhatsAppExport]] = {}

        for zip_file_path in self.config.zip_files:
            zip_path = Path(zip_file_path)
            if not zip_path.exists():
                raise FileNotFoundError(f"ZIP file not found: {zip_path}")

            if num_files > 1:
                logger.info(f"  📦 {zip_path}")

            with zipfile.ZipFile(zip_path, "r") as zf:
                # Find the chat file (should be the .txt file)
                txt_files = [f for f in zf.namelist() if f.endswith(".txt")]
                if not txt_files:
                    raise ValueError(f"No .txt file found in {zip_path}")
                chat_file = txt_files[0]  # Use the first (and likely only) .txt file
                media_files = [f for f in zf.namelist() if f != chat_file]

            group_name, group_slug = self._get_group_info(chat_file, num_files)

            # Use current date as export creation date
            # Note: Media extraction no longer depends on this matching message dates
            export_date = date.today()

            export = WhatsAppExport(
                zip_path=zip_path,
                group_name=group_name,
                group_slug=group_slug,
                export_date=export_date,
                chat_file=chat_file,
                media_files=media_files,
            )

            # Add export to the group (allowing multiple exports per group for merging)
            if group_slug not in real_groups:
                real_groups[group_slug] = []
            real_groups[group_slug].append(export)

        # Log merging info if multiple files resulted in same groups
        if num_files > 1:
            for group_slug, exports in real_groups.items():
                if len(exports) > 1:
                    logger.info(f"🔀 Merging {len(exports)} exports into group '{group_slug}'")
        return real_groups

    def _get_group_info(self, chat_file: str, num_files: int) -> tuple[str, GroupSlug]:
        """Get group name and slug."""
        if self.config.group_name:
            group_name = self.config.group_name
        else:
            group_name = self._extract_group_name_from_chat_file(chat_file)
            if num_files == 1:
                logger.info(f"📝 Auto-detected group name: {group_name}")
            else:
                logger.info(f"    📝 Auto-detected group name: {group_name}")

        if self.config.group_slug:
            group_slug = self.config.group_slug
        else:
            group_slug = self._generate_group_slug(group_name)
            if num_files == 1:
                logger.info(f"🔗 Auto-generated slug: {group_slug}")
            else:
                logger.info(f"    🔗 Auto-generated slug: {group_slug}")
        return group_name, group_slug

    def _create_virtual_groups(
        self,
        real_groups: dict[GroupSlug, list[WhatsAppExport]],
    ) -> dict[GroupSlug, GroupSource]:
        """Create virtual groups from real groups."""
        virtual_groups = create_virtual_groups(real_groups, self.config.merges)

        if virtual_groups:
            logger.info(f"🔀 Created {len(virtual_groups)} virtual group(s):")
            for slug, source in virtual_groups.items():
                logger.info(f"  • {source.name} ({slug}): merges {len(source.exports)} exports")
        return virtual_groups

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

    def _filter_sources(
        self,
        all_sources: dict[GroupSlug, GroupSource],
    ) -> dict[GroupSlug, GroupSource]:
        """Filter sources to process."""

        if not self.config.skip_real_if_in_virtual:
            return all_sources

        groups_in_merges: set[GroupSlug] = set()
        for merge_config in self.config.merges.values():
            groups_in_merges.update(merge_config.source_groups)

        filtered: dict[GroupSlug, GroupSource] = {}
        for slug, source in all_sources.items():
            if source.is_virtual or slug not in groups_in_merges:
                filtered[slug] = source
            else:
                logger.info(f"  ⏭️  Skipping {source.name} (part of virtual group)")

        return filtered

    def _existing_daily_posts(self, site_root: Path) -> list[Path]:
        """Return existing daily posts for *site_root* if they are present."""

        posts_dir = site_root / "posts"
        if not posts_dir.exists():
            return []

        return [path for path in posts_dir.glob("*.md") if path.is_file() and path.name != "index.md"]

    def _write_group_index(
        self,
        source: GroupSource,
        site_root: Path,
        post_paths: list[Path],
    ) -> None:
        """Update the blog index with generated posts. With Material blog plugin, this is mostly handled automatically."""
        
        # The blog plugin handles post indexing automatically, so we just ensure
        # the posts directory structure is correct
        posts_dir = site_root / "posts"
        if not posts_dir.exists():
            posts_dir.mkdir(parents=True, exist_ok=True)

    def _process_source(  # noqa: PLR0912, PLR0915
        self,
        source: GroupSource,
        *,
        days: int | None,
        from_date: date | None,
        to_date: date | None,
    ) -> list[Path]:
        """Process a single source."""

        # Use flat structure instead of nested group directories
        site_root = self.config.posts_dir
        site_root.mkdir(parents=True, exist_ok=True)

        # Posts go directly into posts/ directory
        daily_dir = site_root / "posts"
        daily_dir.mkdir(parents=True, exist_ok=True)

        # Media and profiles at root level
        media_dir = site_root / "media"
        media_dir.mkdir(parents=True, exist_ok=True)

        profiles_base = site_root / "profiles"
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

        if self.config.anonymization.enabled:
            profile_link_base = (
                self.config.profiles.profile_base_url
                if self.config.profiles.link_members_in_posts
                else None
            )
            full_df = Anonymizer.anonymize_dataframe(
                full_df,
                format=self.config.anonymization.output_format,
                profile_link_base=profile_link_base,
            )

        if full_df.is_empty():
            logger.warning("  No messages found")
            return []

        available_dates = sorted({d for d in full_df.get_column("date").to_list()})
        target_dates = _filter_target_dates(
            available_dates,
            from_date=from_date,
            to_date=to_date,
            days=days,
        )

        results = []
        extractor = MediaExtractor(site_root, group_slug=source.slug)

        # Simplified approach: since we only have one export per group in the new CLI,
        # we can extract media from all exports for any target date
        available_exports = source.exports

        for target_date in target_dates:
            output_path = daily_dir / f"{target_date}.md"
            if self.config.skip_existing_posts and output_path.exists():
                logger.info(
                    f"  ⏭️  Skipping {target_date}: post already exists at {output_path.name}"
                )
                results.append(output_path)
                continue

            logger.info(f"  Processing {target_date}...")

            df_day = full_df.filter(pl.col("date") == target_date).sort("timestamp")

            if df_day.is_empty():
                logger.warning("    Empty transcript")
                continue

            attachment_names = MediaExtractor.find_attachment_names_dataframe(df_day)
            all_media: dict[str, MediaFile] = {}
            if attachment_names:
                remaining = set(attachment_names)
                # Try to extract from all available exports (typically just one)
                for export in available_exports:
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

            _, previous_post = _load_previous_post(daily_dir, target_date)

            # Enrichment
            enrichment_section = None
            enrichment_result: EnrichmentResult | None = None
            if self.config.enrichment.enabled:
                cache: Cache | None = None
                if self.config.cache.enabled:
                    try:
                        cache = _create_cache(
                            self.config.cache.cache_dir,
                            self.config.cache.max_disk_mb,
                        )
                        if self.config.cache.auto_cleanup_days:
                            _cleanup_cache(cache, self.config.cache.auto_cleanup_days)
                    except Exception:
                        cache = None
                enricher = ContentEnricher(
                    self.config.enrichment,
                    cache=cache,
                )
                enrichment_result = asyncio.run(
                    enricher.enrich_dataframe(
                        df_day,
                        client=self.generator.client,
                        target_dates=[target_date],
                        media_files=all_media,
                    )
                )
                enrichment_section = enrichment_result.format_for_prompt(
                    self.config.enrichment.relevance_threshold
                )

            _apply_media_captions_from_enrichment(all_media, enrichment_result)

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
            transcript = render_transcript(
                df_render,
                use_tagged=source.is_virtual,
                prefer_original_line=False,
            )

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

            # RAG
            rag_context = None
            if self.config.rag.enabled:
                rag = ChromadbRAG(config=self.config.rag, source=source)

                # Index raw messages in the vector store without storing plaintext
                try:
                    rag.upsert_messages(df_day, group_slug=source.slug)
                except Exception as exc:  # pragma: no cover - defensive: vector store errors
                    logger.warning("    [RAG] Falha ao indexar mensagens no ChromaDB: %s", exc)

                # Index all generated posts before searching
                rag.index_files(daily_dir, group_slug=source.slug)

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
                    query_gen = QueryGenerator(
                        self.config.rag,
                        keyword_provider=keyword_provider,
                    )
                    query = query_gen.generate(transcript)
                    search_results = rag.search(query.search_query, group_slug=source.slug)
                    if search_results and search_results["documents"]:
                        rag_context = "\n\n".join(
                            f"<<<CONTEXTO_{i}>>>\n{doc}"
                            for i, doc in enumerate(search_results["documents"][0], 1)
                        )

            context = PostContext(
                group_name=source.name,
                transcript=transcript,
                target_date=target_date,
                previous_post=previous_post,
                enrichment_section=enrichment_section,
                rag_context=rag_context,
            )
            # Progressive processing: handle quota errors gracefully
            try:
                logger.info(f"    🤖 Generating post with Gemini for {target_date}...")
                post = self.generator.generate(source, context)
            except RuntimeError as exc:
                if "Quota de API do Gemini esgotada" in str(exc):
                    logger.warning(
                        f"    ⚠️ Quota esgotada ao processar {target_date}. "
                        f"Posts salvos: {len(results)}. "
                        f"Para continuar, tente novamente mais tarde."
                    )
                    # Return partial results - what we've processed so far
                    break
                raise
            except Exception as exc:  # noqa: BLE001
                if _is_transient_gemini_error(exc):
                    logger.warning(
                        "    ⚠️ Gemini indisponível ao gerar post de %s; seguindo para a próxima data.",
                        target_date,
                    )
                    continue
                raise

            try:
                validate_newsletter_privacy(post)
            except PrivacyViolationError as exc:
                raise PrivacyViolationError(
                    f"Privacy violation detected for {source.slug} on {target_date:%Y-%m-%d}: {exc}"
                ) from exc

            media_section = MediaExtractor.format_media_section(
                all_media,
                public_paths=public_paths,
            )
            if media_section:
                post = f"{post.rstrip()}\n\n## Mídias Compartilhadas\n{media_section}\n"

            # Merge Gemini-generated frontmatter with programmatic metadata
            post = _ensure_blog_front_matter(
                post, source=source, target_date=target_date, config=self.config
            )

            # Add profile links to member mentions
            post = _add_member_profile_links(
                post,
                config=self.config,
                source=source,
                repository=profile_repository,
            )

            post = format_markdown(post, assume_front_matter=True)

            logger.info(f"    💾 Saving post to {output_path.name}")
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

        self._write_group_index(source, site_root, results)
        return results

    def _update_profiles_for_day(  # noqa: PLR0912, PLR0915
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
            logger.info("    Unable to load dataframe for profiles: %s", exc)
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

            member_uuid = str(raw_author).strip().lower()
            if not member_uuid:
                continue
            member_label = member_uuid.split("-")[0].upper()
            current_profile = repository.load(member_uuid)

            should_consider, _ = updater.should_update_profile_dataframe(
                member_uuid,
                current_profile,
                df_day,
            )
            if not should_consider:
                continue

            try:
                should_update, reasoning, highlights, insights = asyncio.run(
                    updater.should_update_profile(
                        member_id=member_uuid,
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
                        member_uuid=member_uuid,
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

            if profile is None:
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

    async def _async_update_profile(  # noqa: PLR0913
        self,
        *,
        updater: ProfileUpdater,
        member_label: str,
        member_uuid: str,
        current_profile,
        highlights,
        insights,
        conversation: str,
        context_block: str,
        client,
    ) -> ParticipantProfile | None:
        if current_profile is None:
            return await updater.rewrite_profile(
                member_id=member_uuid,
                old_profile=None,
                recent_conversations=[context_block],
                participation_highlights=highlights,
                interaction_insights=insights,
                gemini_client=client,
            )

        return await updater.append_profile(
            member_id=member_uuid,
            current_profile=current_profile,
            recent_conversations=[context_block],
            participation_highlights=highlights,
            interaction_insights=insights,
            gemini_client=client,
        )

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
            blocks.append("### Post do dia\n" + post_text.strip())
        return "\n\n".join(blocks)

    def _get_profiles_client(self):
        if self._profile_updater is None:
            return None
        try:
            return self.generator.client
        except RuntimeError as exc:
            logger.warning("    ⚠️ Perfis desativados: %s", exc)
            return None

    def list_groups(self) -> dict[GroupSlug, dict[str, object]]:
        """List discovered groups."""

        # real_groups = discover_groups(self.config.zips_dir)
        real_groups = {}
        virtual_groups = create_virtual_groups(real_groups, self.config.merges)

        all_info: dict[GroupSlug, dict[str, object]] = {}

        for slug, exports in real_groups.items():
            dates = [e.export_date for e in exports]
            all_info[slug] = {
                "name": exports[0].group_name,
                "type": "real",
                "export_count": len(exports),
                "date_range": (min(dates), max(dates)),
                "in_virtual": [s for s, c in self.config.merges.items() if slug in c.source_groups],
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