"""Core post generation pipeline."""

from __future__ import annotations

import logging
import os
import re
import zipfile
from collections.abc import Sequence
from datetime import date, datetime, timedelta, tzinfo
from importlib import resources
from pathlib import Path

try:  # pragma: no cover - executed only when dependency is missing
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - allows importing without dependency
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

import polars as pl
from diskcache import Cache

from .anonymizer import Anonymizer
from .config import PipelineConfig
from .media_extractor import MediaExtractor, MediaFile
from .system_classifier import SystemMessageClassifier
from .types import GroupSlug

DATE_IN_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_BASE_PROMPT_NAME = "system_instruction_base.md"
_MULTIGROUP_PROMPT_NAME = "system_instruction_multigroup.md"


def _create_cache(directory: Path, size_limit_mb: int | None) -> Cache:
    directory.mkdir(parents=True, exist_ok=True)
    size_limit_bytes = 0 if size_limit_mb is None else max(0, int(size_limit_mb)) * 1024 * 1024
    return Cache(directory=str(directory), size_limit=size_limit_bytes)


def _emit(
    message: str,
    *,
    logger: logging.Logger | None = None,
    batch_mode: bool = False,
    level: str = "info",
) -> None:
    """Emit a log message respecting batch execution preferences."""

    if logger is not None:
        log_func = getattr(logger, level, logger.info)
        log_func(message)
    elif not batch_mode:
        print(message)


def _load_prompt(filename: str) -> str:
    """Load a prompt either from the editable folder or the package data."""

    local_prompt_path = _PROMPTS_DIR / filename
    if local_prompt_path.exists():
        text = local_prompt_path.read_text(encoding="utf-8")
        stripped = text.strip()
        if not stripped:
            raise ValueError(f"Prompt file '{local_prompt_path}' is empty")
        return stripped

    try:
        package_text = (
            resources.files(__package__).joinpath(f"prompts/{filename}").read_text(encoding="utf-8")
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Prompt file '{filename}' is missing.") from exc

    stripped = package_text.strip()
    if not stripped:
        raise ValueError(f"Prompt resource '{filename}' is empty")
    return stripped


TRANSCRIPT_PATTERNS = [
    re.compile(
        r"^(?P<prefix>\d{1,2}:\d{2}\s[-–—]\s)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"
    ),
    re.compile(
        r"^(?P<prefix>\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}\s[-–—]\s)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"
    ),
    re.compile(
        r"^(?P<prefix>\[\d{1,2}:\d{2}:\d{2}\]\s)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"
    ),
    re.compile(
        r"^(?P<prefix>\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s+[-–—]\s+)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"
    ),
]


def _build_system_classifier(
    config: PipelineConfig,
    classifier: SystemMessageClassifier | None = None,
) -> SystemMessageClassifier | None:
    if classifier is not None:
        return classifier
    if not config.system_classifier.enabled:
        return None

    cache: Cache | None = None
    if config.cache.enabled:
        cache_dir = config.cache.cache_dir / "system_labels"
        try:
            cache = _create_cache(cache_dir, config.cache.max_disk_mb)
        except Exception:
            cache = None

    try:
        return SystemMessageClassifier(
            cache=cache,
            model_name=config.system_classifier.model,
            max_llm_calls=config.system_classifier.max_llm_calls,
            token_budget=config.system_classifier.token_budget,
            retry_attempts=config.system_classifier.retry_attempts,
        )
    except Exception:
        return None


def _anonymize_transcript_line(
    line: str,
    *,
    anonymize: bool,
    format: str = "human",
) -> str:
    """Return ``line`` with the author anonymized when enabled."""

    if not anonymize:
        return line

    for pattern in TRANSCRIPT_PATTERNS:
        match = pattern.match(line)
        if not match:
            continue

        prefix = match.group("prefix")
        author = match.group("author").strip()
        separator = match.group("separator")
        message = match.group("message")

        if author:
            anonymized = Anonymizer.anonymize_author(author, format)
        else:
            anonymized = author

        return f"{prefix}{anonymized}{separator}{message}"

    return line


def _prepare_transcripts(
    transcripts: Sequence[tuple[date, str]],
    config: PipelineConfig,
    *,
    logger: logging.Logger | None = None,
    batch_mode: bool = False,
    classifier: SystemMessageClassifier | None = None,
) -> list[tuple[date, str]]:
    """Return transcripts with authors anonymized when enabled."""

    sanitized: list[tuple[date, str]] = []
    anonymized_authors: set[str] = set()
    processed_lines = 0

    for transcript_date, raw_text in transcripts:
        if not config.anonymization.enabled or not raw_text:
            sanitized.append((transcript_date, raw_text))
            continue

        processed_parts: list[str] = []
        for raw_line in raw_text.splitlines(keepends=True):
            if raw_line.endswith("\n"):
                line = raw_line[:-1]
                newline = "\n"
            else:
                line = raw_line
                newline = ""

            anonymized = _anonymize_transcript_line(
                line,
                anonymize=config.anonymization.enabled,
                format=config.anonymization.output_format,
            )
            processed_parts.append(anonymized + newline)

            processed_lines += 1
            for pattern in TRANSCRIPT_PATTERNS:
                match = pattern.match(line)
                if not match:
                    continue

                author = match.group("author").strip()
                if author:
                    anonymized_authors.add(author)
                break

        sanitized.append((transcript_date, "".join(processed_parts)))

    if config.anonymization.enabled:
        _emit(
            "[Anonimização] "
            f"{len(anonymized_authors)} remetentes anonimizados em {processed_lines} linhas.",
            logger=logger,
            batch_mode=batch_mode,
        )

    classifier_instance = _build_system_classifier(config, classifier)
    if classifier_instance is not None:
        filtered: list[tuple[date, str]] = []
        for transcript_date, sanitized_text in sanitized:
            text = sanitized_text or ""
            cleaned_text, _ = classifier_instance.filter_transcript(text)
            filtered.append((transcript_date, cleaned_text))
        sanitized = filtered

    return sanitized


def _format_transcript_section_header(transcript_count: int) -> str:
    """Return a localized header describing the transcript coverage."""

    if transcript_count <= 1:
        return "TRANSCRITO BRUTO DO ÚLTIMO DIA (NA ORDEM CRONOLÓGICA POR DIA):"
    return f"TRANSCRITO BRUTO DOS ÚLTIMOS {transcript_count} DIAS (NA ORDEM CRONOLÓGICA POR DIA):"


def _prepare_transcripts_sample(
    transcripts: Sequence[tuple[date, str]],
    *,
    max_chars: int,
) -> str:
    """Concatenate recent transcripts limited to ``max_chars`` characters."""

    if max_chars <= 0:
        return ""

    ordered = sorted(transcripts, key=lambda item: item[0], reverse=True)
    collected: list[str] = []
    remaining = max_chars

    for _, text in ordered:
        snippet = text.strip()
        if not snippet:
            continue

        if len(snippet) > remaining:
            snippet = snippet[:remaining]
        collected.append(snippet)
        remaining -= len(snippet)
        if remaining <= 0:
            break

    return "\n\n".join(collected).strip()


def build_llm_input(  # noqa: PLR0913
    *,
    group_name: str,
    timezone: tzinfo,
    transcripts: Sequence[tuple[date, str]],
    previous_post: str | None,
    enrichment_section: str | None = None,
    rag_context: str | None = None,
) -> str:
    """Compose the user prompt sent to Gemini."""

    today_str = datetime.now(timezone).date().isoformat()
    sections: list[str] = [
        f"NOME DO GRUPO: {group_name}",
        f"DATA DE HOJE: {today_str}",
    ]

    if previous_post:
        sections.extend(
            [
                "POST DO DIA ANTERIOR (INCLUA COMO CONTEXTO, NÃO COPIE):",
                "<<<POST_ONTEM_INICIO>>>",
                previous_post.strip(),
                "<<<POST_ONTEM_FIM>>>",
            ]
        )
    else:
        sections.append("POST DO DIA ANTERIOR: NÃO ENCONTRADA")

    if enrichment_section:
        sections.extend(
            [
                "CONTEXTOS ENRIQUECIDOS DOS LINKS COMPARTILHADOS:",
                enrichment_section,
            ]
        )

    if rag_context:
        sections.extend(
            [
                "CONTEXTOS HISTÓRICOS DE POSTS RELEVANTES:",
                rag_context,
            ]
        )

    header = _format_transcript_section_header(len(transcripts))
    sections.append(header)

    for transcript_date, transcript_text in transcripts:
        content = transcript_text.strip()
        sections.extend(
            [
                f"<<<TRANSCRITO_{transcript_date.isoformat()}_INICIO>>>",
                content if content else "(vazio)",
                f"<<<TRANSCRITO_{transcript_date.isoformat()}_FIM>>>",
            ]
        )

    return "\n\n".join(sections)


def _require_google_dependency() -> None:
    """Ensure the optional google-genai dependency is available."""

    if genai is None or types is None:
        raise RuntimeError(
            "A dependência opcional 'google-genai' não está instalada. "
            "Instale-a para gerar posts (ex.: `pip install google-genai`)."
        )


def create_client(api_key: str | None = None):  # pragma: no cover - thin wrapper
    """Create a Gemini client using the provided or environment API key."""

    _require_google_dependency()
    key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("Defina GEMINI_API_KEY ou GOOGLE_API_KEY no ambiente.")
    return genai.Client(api_key=key)


def find_date_in_name(path: Path) -> date | None:
    """Return the first YYYY-MM-DD date embedded in a filename."""

    match = DATE_IN_NAME_RE.search(path.name)
    if not match:
        return None

    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def list_zip_days(zips_dir: Path) -> list[tuple[date, Path]]:
    """Return available zip archives sorted by date."""

    zips: list[tuple[date, Path]] = []
    for path in zips_dir.glob("*.zip"):
        found_date = find_date_in_name(path)
        if found_date is not None:
            zips.append((found_date, path))
    zips.sort(key=lambda item: item[0])
    return zips


def read_zip_texts_and_media(
    zippath: Path,
    *,
    archive_date: date | None = None,
    posts_dir: Path | None = None,
    group_slug: GroupSlug | None = None,
) -> tuple[str, dict[str, MediaFile]]:
    """Read texts from *zippath* and optionally extract media files."""

    extractor: MediaExtractor | None = None
    media_files: dict[str, MediaFile] = {}

    if archive_date is not None:
        if (posts_dir is None) != (group_slug is None):
            raise ValueError(
                "posts_dir and group_slug must both be provided to extract media",
            )
        if posts_dir is not None and group_slug is not None:
            group_dir = posts_dir / group_slug
            extractor = MediaExtractor(group_dir, group_slug=group_slug)
            media_files = extractor.extract_media_from_zip(zippath, archive_date)

    chunks: list[str] = []
    with zipfile.ZipFile(zippath, "r") as zipped:
        txt_names = sorted(name for name in zipped.namelist() if name.lower().endswith(".txt"))
        for name in txt_names:
            with zipped.open(name, "r") as file_handle:
                raw = file_handle.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
            text = text.replace("\r\n", "\n")
            chunks.append(f"\n# Arquivo: {name}\n{text.strip()}\n")

    transcript = "\n".join(chunks).strip()
    if extractor is not None and media_files:
        frame = pl.DataFrame({"message": transcript.splitlines()})
        replaced = MediaExtractor.replace_media_references_dataframe(frame, media_files)
        transcript = "\n".join(replaced["message"].to_list())
    return transcript, media_files


def load_previous_post(
    posts_dir: Path,
    reference_date: date,
    *,
    search_window_days: int = 7,
) -> tuple[Path, str | None]:
    """Return the most recent post prior to ``reference_date``.

    The previous implementation only considered "yesterday" and silently ignored
    gaps in the archive. During the migration from newsletters to posts we found
    several groups that published twice a week, leaving holes in the
    day-to-day timeline. The pipeline expects to reuse the latest available
    context regardless of that cadence, so we now look backwards up to
    ``search_window_days`` and return the first file that exists. The returned
    path always points to the file that satisfied the search; if no file is
    found we fall back to the expected location for the immediate previous day
    so callers can still write a brand-new document there.
    """

    if search_window_days < 1:
        raise ValueError("search_window_days must be at least 1 day")

    target_path = posts_dir / f"{(reference_date - timedelta(days=1)).isoformat()}.md"

    for delta in range(1, search_window_days + 1):
        candidate_date = reference_date - timedelta(days=delta)
        candidate_path = posts_dir / f"{candidate_date.isoformat()}.md"
        if candidate_path.exists():
            return candidate_path, candidate_path.read_text(encoding="utf-8")

    return target_path, None


def ensure_directories(config: PipelineConfig) -> None:
    """Ensure required directories exist."""

    config.posts_dir.mkdir(parents=True, exist_ok=True)
    config.zips_dir.mkdir(parents=True, exist_ok=True)


def select_recent_archives(
    archives: Sequence[tuple[date, Path]], *, days: int
) -> list[tuple[date, Path]]:
    """Select the most recent archives respecting *days*."""

    if days <= 0:
        raise ValueError("days must be positive")
    return list(archives[-days:]) if len(archives) >= days else list(archives)


def read_zip_texts(zippath: Path) -> str:
    """Backward-compatible wrapper returning only text transcripts."""

    transcript, _ = read_zip_texts_and_media(zippath)
    return transcript


__all__ = [
    "build_llm_input",
    "create_client",
    "ensure_directories",
    "find_date_in_name",
    "list_zip_days",
    "load_previous_post",
    "read_zip_texts",
    "read_zip_texts_and_media",
    "select_recent_archives",
    "_anonymize_transcript_line",
    "_format_transcript_section_header",
    "_load_prompt",
    "_prepare_transcripts",
    "_prepare_transcripts_sample",
]
