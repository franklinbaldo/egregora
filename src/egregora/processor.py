"Unified processor with Polars-based message manipulation."

from __future__ import annotations

import asyncio
import logging
import re
import textwrap
import unicodedata
import uuid
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

import polars as pl
import yaml
from diskcache import Cache

from .anonymizer import Anonymizer
from .config import PipelineConfig
from .gemini_manager import GeminiManager
from .generator import PostContext, PostGenerator
from .markdown_utils import format_markdown


from .media_extractor import MediaExtractor, MediaFile
from .merger import create_virtual_groups, get_merge_stats
from .models import GroupSource, WhatsAppExport
from .privacy import PrivacyViolationError, validate_newsletter_privacy
from .profiles import ParticipantProfile, ProfileRepository, ProfileUpdater
from .rag.chromadb_rag import ChromadbRAG
from .schema import ensure_message_schema
from .transcript import (
    load_source_dataframe,
    render_transcript,
)
from .types import GroupSlug
from .zip_utils import ZipValidationLimits, configure_default_limits

try:  # pragma: no cover - optional dependency
    from google.genai import errors as genai_errors
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    genai_errors = None  # type: ignore[assignment]

try:  # Simple enricher imports for enrichment functionality
    from .simple_enricher import (
        save_media_enrichment,
        save_simple_enrichment,
        simple_enrich_media_with_cache,
        simple_enrich_url_with_cache,
    )
except ImportError:  # pragma: no cover - optional dependency
    simple_enrich_url_with_cache = None  # type: ignore[assignment]
    save_simple_enrichment = None  # type: ignore[assignment]
    save_media_enrichment = None  # type: ignore[assignment]
    simple_enrich_media_with_cache = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from .enrichment import EnrichmentResult

logger = logging.getLogger(__name__)

YAML_DELIMITER = "---"

_TRANSIENT_STATUS_CODES = {500, 502, 503, 504}
MAX_MEDIA_CAPTION_LENGTH = 160
_FRONT_MATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_CODE_BLOCK_FRONT_MATTER_PATTERN = re.compile(
    r"```(?:yaml)?\s*\n---\s*\n(.*?)\n---\s*\n```\s*\n?",
    re.DOTALL,
)


def _is_transient_gemini_error(exc: Exception) -> bool:
    """Return ``True`` when *exc* looks like a temporary Gemini outage."""
    # FIXME: String matching on error messages is brittle. This should be updated
    # if the Gemini library provides more specific exception types or error codes.
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


def _cleanup_cache(cache: Cache, max_age_days: int) -> None:
    """Remove cache entries older than max_age_days."""

    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)

    try:
        for key in list(cache):
            try:
                entry = cache.get(key)
            except Exception:
                continue

            if not isinstance(entry, dict):
                continue

            last_used = _coerce_timestamp(entry.get("last_used"))
            if last_used is None:
                payload = entry.get("payload")
                if isinstance(payload, dict):
                    last_used = _coerce_timestamp(payload.get("last_used"))

            if last_used is not None and last_used < cutoff:
                try:
                    cache.delete(key)
                except Exception:
                    continue

        cache.cull()
    except Exception:
        cache.cull()


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


def _safe_load_mapping(raw_yaml: str) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _extract_front_matter(text: str) -> tuple[dict[str, Any], str]:
    stripped = text.lstrip()
    metadata: dict[str, Any] = {}
    remaining = stripped

    match = _FRONT_MATTER_PATTERN.match(stripped)
    if match:
        metadata = _safe_load_mapping(match.group(1))
        remaining = stripped[match.end() :]

    cleaned = _CODE_BLOCK_FRONT_MATTER_PATTERN.sub("", remaining)
    return metadata, cleaned.lstrip()


def _ensure_blog_front_matter(
    text: str, *, source: GroupSource, target_date: date, config: PipelineConfig
) -> str:
    """Merge Gemini-generated frontmatter with programmatic metadata."""

    user_metadata, body = _extract_front_matter(text)
    programmatic = _build_post_metadata(source, target_date, config)
    merged_metadata = {**programmatic, **user_metadata}

    front_matter = yaml.safe_dump(merged_metadata, sort_keys=False, allow_unicode=True).strip()
    content = body.lstrip()
    return (
        f"{YAML_DELIMITER}\n{front_matter}\n{YAML_DELIMITER}\n\n{content}"
        if content
        else f"{YAML_DELIMITER}\n{front_matter}\n{YAML_DELIMITER}\n"
    )


def _mark_post_as_draft(post_text: str, privacy_reason: str) -> str:
    """Mark a post as draft due to privacy violation."""
    
    metadata, body = _extract_front_matter(post_text)
    
    # Add draft flag and privacy note
    metadata["draft"] = True
    metadata["privacy_warning"] = f"DRAFT - Privacy issue detected: {privacy_reason}"
    
    # Regenerate post with updated metadata
    front_matter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()
    content = body.lstrip()
    
    return (
        f"{YAML_DELIMITER}\n{front_matter}\n{YAML_DELIMITER}\n\n{content}"
        if content
        else f"{YAML_DELIMITER}\n{front_matter}\n{YAML_DELIMITER}\n"
    )


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
        rf"(?P<link>\[[^]]+\]\([^)]+\))\s*(?P<uuid>{uuid_pattern})",
        re.IGNORECASE,
    )
    # Match UUIDs in parentheses that are NOT in media section or file paths
    paren_uuid = re.compile(rf"\((?P<uuid>{uuid_pattern})\)", re.IGNORECASE)
    # Match bare UUIDs that are NOT followed by file extensions
    bare_uuid = re.compile(rf"(?<![\w-])(?P<uuid>{uuid_pattern})(?![\w-])", re.IGNORECASE)

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

    for extra_dir in config.profiles.link_directories:
        try:
            for profile_file in extra_dir.glob("*.md"):
                if profile_file.name.lower() == "index.md":
                    continue
                profile_files[profile_file.stem.lower()] = profile_file
        except Exception:
            continue

    def _resolve_profile(uuid_value: str) -> str | None:
        identifier = uuid_value.lower()
        candidate_path = profile_files.get(identifier)
        if candidate_path is not None and candidate_path.exists():
            # Use consistent relative path format: profiles/{uuid}.md
            return f"profiles/{identifier}.md"

        # Always use consistent relative path format
        return f"profiles/{identifier}.md"

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
        before_context = text[max(0, start_pos - 100) : start_pos]
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
        before_context = text[max(0, start_pos - 100) : start_pos]
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

        configure_default_limits(
            ZipValidationLimits(
                max_total_size=self.config.zip_validation.max_total_size,
                max_member_size=self.config.zip_validation.max_member_size,
                max_member_count=self.config.zip_validation.max_member_count,
            )
        )

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



    def _extract_group_name_from_chat_file(self, chat_filename: str) -> str:
        """Extract group name from WhatsApp chat filename."""
        # Pattern: "Conversa do WhatsApp com GROUP_NAME.txt"

        # Remove file extension
        base_name = chat_filename.replace(".txt", "")

        for pattern in self.config.group_name_patterns:
            match = re.search(pattern, base_name, re.IGNORECASE)
            if match:
                group_name = match.group(1).strip()
                # Remove common suffixes like dates, emojis at the end
                group_name = re.sub(r"\s*[\U0001f000-\U0001f0ff]+\s*$", "", group_name).strip()
                return group_name

        # Fallback: use the whole filename without extension
        return base_name

    def _generate_group_slug(self, group_name: str) -> str:
        """Generate a URL-friendly slug from group name."""

        # Normalize unicode characters
        slug = unicodedata.normalize("NFKD", group_name)
        slug = slug.encode("ascii", "ignore").decode("ascii")

        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r"[^\\w\s-]", "", slug.lower())
        slug = re.sub(r"[-\s]+", "-", slug)

        # Remove leading/trailing hyphens
        slug = slug.strip("-")

        if not slug:
            fallback = re.sub(r"[^-]+", "-", group_name.lower()).strip("-")
            slug = fallback or f"whatsapp-group-{abs(hash(group_name)) & 0xFFFF:04x}"

        slug = slug[:64].strip("-")
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

        posts_dir = site_root / self.config.site.full_blog_path
        if not posts_dir.exists():
            return []

        return [
            path for path in posts_dir.glob("*.md") if path.is_file() and path.name != "index.md"
        ]

    def _write_group_index(
        self,
        source: GroupSource,
        site_root: Path,
        post_paths: list[Path],
    ) -> None:
        """Update the blog index with generated posts. With Material blog plugin, this is mostly handled automatically."""

        # The blog plugin handles post indexing automatically, so we just ensure
        # the posts directory structure is correct
        posts_dir = site_root / self.config.site.full_blog_path
        if not posts_dir.exists():
            posts_dir.mkdir(parents=True, exist_ok=True)

    # TODO: This function is too long and complex. It should be refactored into
    # smaller, more manageable functions.
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

        # Posts go into blog/posts/ directory using SiteConfig
        daily_dir = site_root / self.config.site.full_blog_path
        daily_dir.mkdir(parents=True, exist_ok=True)

        # Unified structure: place both media and profiles inside docs/ directory
        output_root = site_root.parent if site_root.name == self.config.site.docs_dir else site_root
        media_dir = site_root / "media"  # Move media inside docs/
        media_dir.mkdir(parents=True, exist_ok=True)

        # Place profiles inside docs/ directory for proper relative linking
        profiles_base = site_root / "profiles"  
        profiles_base.mkdir(parents=True, exist_ok=True)

        profile_repository = None
        if self.config.profiles.enabled and self._profile_updater:
            profile_repository = ProfileRepository(
                data_dir=profiles_base / "json",
                docs_dir=profiles_base,
            )

        # Collect all unique authors for .authors.yml generation
        all_authors: set[str] = set()

        try:
            full_df = load_source_dataframe(source)
        except ValueError as exc:
            logger.warning("  Unable to load messages for %s: %s", source.slug, exc)
            return []

        print(f"Anonymization enabled: {self.config.anonymization.enabled}")
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
        # Use the unified media directory inside docs/
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

            # Simple enrichment - add enrichments as messages to dataframe
            if self.config.enrichment.enabled and simple_enrich_url_with_cache is not None:
                try:
                    # Setup cache
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

                    # Extract and sanitize URLs from the day's messages using a declarative flow
                    url_matches = (
                        df_day.select(
                            "timestamp",
                            "author",
                            "message",
                            pl.col("message")
                            .cast(pl.Utf8)
                            .fill_null("")
                            .str.extract_all(r"(https?://[^->)]+)")
                            .alias("__urls"),
                        )
                        .explode("__urls")
                        .rename({"__urls": "url"})
                        .drop_nulls("url")
                        .with_columns(
                            pl.col("url")
                            .str.replace(r"\s+.*$", "")
                            .str.strip_chars()
                            .alias("url")
                        )
                        .filter(pl.col("url") != "")
                        .sort("timestamp")
                    )

                    if url_matches.is_empty():
                        deduped_urls = pl.DataFrame(
                            schema={
                                "urls": pl.Utf8,
                                "timestamp": df_day.schema.get(
                                    "timestamp", pl.Datetime(time_unit="us")
                                ),
                                "author": pl.Utf8,
                                "message": pl.Utf8,
                            }
                        )
                    else:
                        deduped_urls = (
                            url_matches.group_by("url", maintain_order=True)
                            .agg(
                                pl.col("timestamp").first().alias("timestamp"),
                                pl.col("author").first().alias("author"),
                                pl.col("message").first().alias("message"),
                            )
                            .rename({"url": "urls"})
                        )

                    enrichment_df: pl.DataFrame | None = None

                    if not deduped_urls.is_empty():
                        request_structs = (
                            deduped_urls.with_columns(
                                pl.struct(["urls", "message", "author", "timestamp"]).alias(
                                    "__request"
                                )
                            )
                            .get_column("__request")
                            .to_list()
                        )

                        async def _gather_url_enrichments() -> list[str]:
                            if not request_structs:
                                return []
                            return await asyncio.gather(
                                *[
                                    simple_enrich_url_with_cache(
                                        req["urls"],
                                        req["message"],
                                        cache,
                                    )
                                    for req in request_structs
                                ]
                            )

                        enrichment_texts = asyncio.run(_gather_url_enrichments())

                        for request, enrichment_text in zip(
                            request_structs, enrichment_texts, strict=False
                        ):
                            timestamp = request["timestamp"]
                            save_simple_enrichment(
                                url=request["urls"],
                                enrichment_text=enrichment_text,
                                media_dir=media_dir,
                                sender=request["author"],
                                timestamp=timestamp.strftime("%H:%M") if timestamp else None,
                                date_str=target_date.isoformat(),
                                message=request["message"],
                                media_path=None,
                                media_type=None,
                            )

                        enrichment_df = (
                            deduped_urls.with_columns(
                                pl.Series("__enrichment_text", enrichment_texts),
                                pl.lit(target_date).alias("date"),
                                pl.lit("egregora").alias("author"),
                                pl.lit(None, dtype=pl.Utf8).alias("original_line"),
                                pl.lit(None, dtype=pl.Utf8).alias("tagged_line"),
                            )
                            .with_columns(
                                pl.format(
                                    "📊 Análise de {}:\n\n{}",
                                    pl.col("urls"),
                                    pl.col("__enrichment_text"),
                                ).alias("message")
                            )
                            .select(
                                "timestamp",
                                "date",
                                "author",
                                "message",
                                "original_line",
                                "tagged_line",
                            )
                        )

                    # Prepare normalized message text for media matching
                    df_day_text = df_day.with_columns(
                        pl.col("message")
                        .cast(pl.Utf8)
                        .fill_null("")
                        .alias("__message_text")
                    )

                    # Process media files for enrichment
                    for media_key, media_file in all_media.items():
                        # Ensure we use the actual UUID, not the original filename
                        actual_media_uuid = getattr(media_file, "uuid", media_key)
                        if hasattr(media_file, "dest_path") and media_file.dest_path:
                            # Extract UUID from dest_path filename if available
                            dest_filename = media_file.dest_path.stem  # filename without extension
                            # Check if dest_filename is a valid UUID format
                            try:
                                uuid.UUID(dest_filename)
                                actual_media_uuid = dest_filename
                            except ValueError:
                                # If not a UUID, use the original media_key
                                pass
                        # Get enrichment from LLM for media files

                        # Find the message that references this media
                        matching = df_day_text.filter(
                            pl.col("__message_text").str.contains(re.escape(media_key))
                        )
                        if matching.height > 0:
                            media_message_row = matching.drop("__message_text").row(
                                0, named=True
                            )
                        else:
                            media_message_row = None

                        # Get LLM analysis of the media
                        media_path = getattr(media_file, "dest_path", Path("unknown"))
                        media_type = getattr(media_file, "media_type", "unknown")
                        context_message = (
                            media_message_row.get("message") if media_message_row else ""
                        )

                        media_enrichment = asyncio.run(
                            simple_enrich_media_with_cache(
                                media_path=media_path,
                                media_type=media_type,
                                context_message=context_message,
                                cache=cache,
                            )
                        )

                        save_media_enrichment(
                            media_key=actual_media_uuid,
                            media_path=getattr(media_file, "dest_path", Path("unknown")),
                            media_type=getattr(media_file, "media_type", "unknown"),
                            enrichment_text=media_enrichment,
                            media_dir=media_dir,
                            sender=media_message_row.get("author") if media_message_row else None,
                            timestamp=media_message_row.get("timestamp").strftime("%H:%M")
                            if media_message_row and media_message_row.get("timestamp")
                            else None,
                            date_str=target_date.isoformat(),
                            message=media_message_row.get("message") if media_message_row else None,
                        )

                    # Drop auxiliary matching column after processing
                    df_day_text = df_day_text.drop("__message_text")

                    # Add enriched messages to dataframe
                    if enrichment_df is not None and not enrichment_df.is_empty():
                        enrichment_df = ensure_message_schema(
                            enrichment_df, timezone=self.config.timezone
                        )
                        df_day = pl.concat([df_day, enrichment_df], how="diagonal")
                        df_day = df_day.sort("timestamp")

                        logger.info(
                            f"    🔍 Added {enrichment_df.height} enrichments as messages"
                        )

                except Exception as exc:
                    logger.warning("    ⚠️ Failed to perform simple enrichment: %s", exc)

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

            # Collect unique authors (already anonymized if config.anonymization.enabled)
            day_authors = df_render.get_column("author").unique().to_list()
            all_authors.update(day_authors)

            transcript = render_transcript(
                df_render,
                use_tagged=source.is_virtual,
                prefer_original_line=False,
            )

            # Validate privacy BEFORE sending to LLM
            try:
                validate_newsletter_privacy(transcript)
            except PrivacyViolationError as exc:
                raise PrivacyViolationError(
                    f"Privacy violation detected in transcript for {source.slug} on {target_date:%Y-%m-%d}: {exc}. "
                    f"Check anonymization - sensitive data should not reach LLM."
                ) from exc

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
                rag = ChromadbRAG(config=self.config.rag, source=source, batch_client=self.generator.client)

                # Index raw messages in the vector store without storing plaintext
                try:
                    rag.upsert_messages(df_day, group_slug=source.slug)
                # FIXME: Catching a broad `Exception` can hide bugs. This should be
                # replaced with more specific exception types from the ChromaDB library.
                except Exception as exc:  # pragma: no cover - defensive: vector store errors
                    logger.warning("    [RAG] Falha ao indexar mensagens no ChromaDB: %s", exc)

                # Index all generated posts before searching
                rag.index_files(daily_dir, group_slug=source.slug)

                # Search using whole transcript directly (no keyword extraction)
                try:
                    search_results = rag.search(transcript, group_slug=source.slug)
                    if search_results and search_results["documents"]:
                        rag_context = "\n\n".join(
                            f"<<<CONTEXTO_{i}>>>\n{doc}"
                            for i, doc in enumerate(search_results["documents"][0], 1)
                        )
                except Exception as exc:  # pragma: no cover - defensive: RAG search errors
                    logger.warning("    [RAG] Falha ao buscar contexto: %s", exc)

                # Export embeddings to parquet file in docs/
                try:
                    embeddings_path = site_root / "embeddings.parquet"
                    rag.export_embeddings_to_parquet(embeddings_path)
                except Exception as exc:
                    logger.warning("    [RAG] Failed to export embeddings: %s", exc)

            context = PostContext(
                group_name=source.name,
                transcript=transcript,
                target_date=target_date,
                previous_post=previous_post,
                enrichment_section=None,
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

            # Privacy validation now happens BEFORE LLM call to prevent sending sensitive data

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

        # Regenerate profile index after all days have been processed
        # This ensures the index reflects all profiles even if the last day had no updates
        if profile_repository:
            try:
                profile_repository.write_index()
                logger.info("  📋 Profile index regenerated after processing %d days", len(results))
            except Exception as exc:
                logger.warning("  ⚠️ Failed to regenerate profile index: %s", exc)

        # Generate .authors.yml for mkdocs-material blog plugin
        if all_authors:
            try:
                authors_file_path = site_root / ".authors.yml"
                authors_data = {}
                for author_id in sorted(all_authors):
                    # If anonymization is enabled, author_id is already a UUID
                    # Use it as-is for the key, and extract a human-readable label
                    if self.config.anonymization.enabled:
                        # Extract first 4 chars of UUID as human-readable identifier
                        author_uuid = str(author_id)
                        short_id = author_uuid.split("-")[0][:4].upper()
                        author_name = f"Member-{short_id}"
                    else:
                        # If not anonymized, use author_id directly
                        author_name = str(author_id)
                        author_uuid = str(author_id)

                    authors_data[author_uuid] = {
                        "name": author_name,
                        "description": "Membro do grupo",
                        "url": f"profiles/{author_uuid}.md",  # Link to profile markdown
                    }

                with authors_file_path.open("w", encoding="utf-8") as f:
                    yaml.dump(authors_data, f, allow_unicode=True, sort_keys=False)

                logger.info("  👤 Generated .authors.yml with %d authors", len(authors_data))
            except Exception as exc:
                logger.warning("  ⚠️ Failed to generate .authors.yml: %s", exc)

        return results

    # TODO: This function is too long and complex. It should be refactored into
    # smaller, more manageable functions.
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
                should_update, reasoning, _, _ = asyncio.run(
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
                        member_uuid=member_uuid,
                        current_profile=current_profile,
                        conversation=conversation,
                        recent_conversations=[context_block],
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

    # TODO: This function has too many arguments. It should be refactored,
    # perhaps by using a dataclass for the arguments.
    async def _async_update_profile(
        self,
        *,
        updater: ProfileUpdater,
        member_uuid: str,
        current_profile: ParticipantProfile | None,
        conversation: str,
        recent_conversations: Sequence[str],
        client,
    ) -> ParticipantProfile | None:
        return await updater.update_profile_with_agent(
            member_id=member_uuid,
            current_profile=current_profile,
            full_conversation=conversation,
            recent_conversations=recent_conversations,
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
