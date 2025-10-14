"""Utility helpers retained for the refactored pipeline."""

from __future__ import annotations

import re
import zipfile
from collections.abc import Sequence
from datetime import date, datetime, timedelta, tzinfo
from importlib import resources
from pathlib import Path

import polars as pl

from .config import PipelineConfig
from .ingest.anonymizer import Anonymizer
from .media_extractor import MediaExtractor, MediaFile
from .types import GroupSlug

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_TRANSCRIPT_PATTERNS = [
    re.compile(r"^(?P<prefix>\d{1,2}:\d{2}\s[-–—]\s)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"),
    re.compile(
        r"^(?P<prefix>\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}\s[-–—]\s)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"
    ),
    re.compile(r"^(?P<prefix>\[\d{1,2}:\d{2}:\d{2}\]\s)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"),
    re.compile(
        r"^(?P<prefix>\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s+[-–—]\s+)(?P<author>[^:]+)(?P<separator>:\s*)(?P<message>.*)$"
    ),
]


def _load_prompt(filename: str) -> str:
    """Load prompt text from the editable directory or package resources."""

    local_path = _PROMPTS_DIR / filename
    if local_path.exists():
        text = local_path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError(f"Prompt file '{local_path}' is empty")
        return text

    try:
        resource_text = resources.files("egregora.prompts").joinpath(filename).read_text(encoding="utf-8")
    except FileNotFoundError as exc:  # pragma: no cover - invalid installation
        raise FileNotFoundError(f"Prompt file '{filename}' is missing.") from exc

    stripped = resource_text.strip()
    if not stripped:
        raise ValueError(f"Prompt resource '{filename}' is empty")
    return stripped


def _anonymize_transcript_line(
    line: str,
    *,
    anonymize: bool,
    format: str = "human",
) -> str:
    """Return ``line`` with the author anonymized when enabled."""

    if not anonymize:
        return line

    for pattern in _TRANSCRIPT_PATTERNS:
        match = pattern.match(line)
        if not match:
            continue

        prefix = match.group("prefix")
        author = match.group("author").strip()
        separator = match.group("separator")
        message = match.group("message")

        anonymized = Anonymizer.anonymize_author(author, format) if author else author
        return f"{prefix}{anonymized}{separator}{message}"

    return line


def _prepare_transcripts(
    transcripts: Sequence[tuple[date, str]],
    config: PipelineConfig,
    *,
    logger=None,  # kept for backward-compatible signature
    batch_mode: bool = False,  # noqa: FBT002 - retained for compatibility
    classifier=None,
) -> list[tuple[date, str]]:
    """Return transcripts with authors anonymized when enabled."""

    sanitized: list[tuple[date, str]] = []

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

        sanitized.append((transcript_date, "".join(processed_parts)))

    if classifier is not None:
        sanitized = [
            (transcript_date, classifier.filter_transcript(text or "")[0])
            for transcript_date, text in sanitized
        ]

    return sanitized


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


def _format_transcript_section_header(transcript_count: int) -> str:
    """Return a localized header describing the transcript coverage."""

    if transcript_count <= 1:
        return "TRANSCRITO BRUTO DO ÚLTIMO DIA (NA ORDEM CRONOLÓGICA POR DIA):"
    return f"TRANSCRITO BRUTO DOS ÚLTIMOS {transcript_count} DIAS (NA ORDEM CRONOLÓGICA POR DIA):"


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


_DATE_IN_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def find_date_in_name(path: Path) -> date | None:
    """Return the first YYYY-MM-DD date embedded in a filename."""

    match = _DATE_IN_NAME_RE.search(path.name)
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
            raise ValueError("posts_dir e group_slug devem ser fornecidos em conjunto para extrair mídia")
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


def read_zip_texts(zippath: Path) -> str:
    """Backward-compatible wrapper returning only text transcripts."""

    transcript, _ = read_zip_texts_and_media(zippath)
    return transcript


def load_previous_post(
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


__all__ = [
    "build_llm_input",
    "find_date_in_name",
    "list_zip_days",
    "load_previous_post",
    "read_zip_texts",
    "read_zip_texts_and_media",
    "_anonymize_transcript_line",
    "_format_transcript_section_header",
    "_load_prompt",
    "_prepare_transcripts",
    "_prepare_transcripts_sample",
]
