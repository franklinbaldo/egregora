"""Core newsletter generation pipeline."""

from __future__ import annotations

import os
import re
import zipfile
from datetime import date, datetime, timedelta, tzinfo
from importlib import resources
from pathlib import Path
from typing import Any, Sequence

import logging

try:  # pragma: no cover - executed only when dependency is missing
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - allows importing without dependency
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

from .anonymizer import Anonymizer
from .config import PipelineConfig
from .media_extractor import MediaExtractor, MediaFile

DATE_IN_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_BASE_PROMPT_NAME = "system_instruction_base.md"
_MULTIGROUP_PROMPT_NAME = "system_instruction_multigroup.md"


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
            resources.files(__package__)
            .joinpath(f"prompts/{filename}")
            .read_text(encoding="utf-8")
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

    return sanitized


def _format_transcript_section_header(transcript_count: int) -> str:
    """Return a localized header describing the transcript coverage."""

    if transcript_count <= 1:
        return "TRANSCRITO BRUTO DO ÚLTIMO DIA (NA ORDEM CRONOLÓGICA POR DIA):"
    return (
        f"TRANSCRITO BRUTO DOS ÚLTIMOS {transcript_count} DIAS "
        "(NA ORDEM CRONOLÓGICA POR DIA):"
    )


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


def build_llm_input(
    *,
    group_name: str,
    timezone: tzinfo,
    transcripts: Sequence[tuple[date, str]],
    previous_newsletter: str | None,
    enrichment_section: str | None = None,
    rag_context: str | None = None,
) -> str:
    """Compose the user prompt sent to Gemini."""

    today_str = datetime.now(timezone).date().isoformat()
    sections: list[str] = [
        f"NOME DO GRUPO: {group_name}",
        f"DATA DE HOJE: {today_str}",
    ]

    if previous_newsletter:
        sections.extend([
            "NEWSLETTER DO DIA ANTERIOR (INCLUA COMO CONTEXTO, NÃO COPIE):",
            "<<<NEWSLETTER_ONTEM_INICIO>>>",
            previous_newsletter.strip(),
            "<<<NEWSLETTER_ONTEM_FIM>>>",
        ])
    else:
        sections.append("NEWSLETTER DO DIA ANTERIOR: NÃO ENCONTRADA")

    if enrichment_section:
        sections.extend([
            "CONTEXTOS ENRIQUECIDOS DOS LINKS COMPARTILHADOS:",
            enrichment_section,
        ])

    if rag_context:
        sections.extend([
            "CONTEXTOS HISTÓRICOS DE NEWSLETTERS RELEVANTES:",
            rag_context,
        ])

    header = _format_transcript_section_header(len(transcripts))
    sections.append(header)

    for transcript_date, transcript_text in transcripts:
        content = transcript_text.strip()
        sections.extend([
            f"<<<TRANSCRITO_{transcript_date.isoformat()}_INICIO>>>",
            content if content else "(vazio)",
            f"<<<TRANSCRITO_{transcript_date.isoformat()}_FIM>>>",
        ])

    return "\n\n".join(sections)


def _require_google_dependency() -> None:
    """Ensure the optional google-genai dependency is available."""

    if genai is None or types is None:
        raise RuntimeError(
            "A dependência opcional 'google-genai' não está instalada. "
            "Instale-a para gerar newsletters (ex.: `pip install google-genai`)."
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
    media_dir: Path | None = None,
) -> tuple[str, dict[str, MediaFile]]:
    """Read texts from *zippath* and optionally extract media files."""

    extractor: MediaExtractor | None = None
    media_files: dict[str, MediaFile] = {}

    if archive_date is not None and media_dir is not None:
        extractor = MediaExtractor(media_dir)
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
    if extractor is not None and transcript:
        transcript = MediaExtractor.replace_media_references(transcript, media_files)

    return transcript, media_files


def read_zip_texts(zippath: Path) -> str:
    """Backward-compatible helper that returns only the transcript text."""

    transcript, _ = read_zip_texts_and_media(zippath)
    return transcript


def load_previous_newsletter(news_dir: Path, reference_date: date) -> tuple[Path, str | None]:
    """Load yesterday's newsletter if it exists."""

    yesterday = reference_date - timedelta(days=1)
    path = news_dir / f"{yesterday.isoformat()}.md"
    if path.exists():
        return path, path.read_text(encoding="utf-8")
    return path, None


def ensure_directories(config: PipelineConfig) -> None:
    """Ensure required directories exist."""

    config.newsletters_dir.mkdir(parents=True, exist_ok=True)
    config.zips_dir.mkdir(parents=True, exist_ok=True)
    config.media_dir.mkdir(parents=True, exist_ok=True)


def select_recent_archives(
    archives: Sequence[tuple[date, Path]], *, days: int
) -> list[tuple[date, Path]]:
    """Select the most recent archives respecting *days*."""

    if days <= 0:
        raise ValueError("days must be positive")
    return list(archives[-days:]) if len(archives) >= days else list(archives)


__all__ = [
    "build_llm_input",
    "create_client",
    "ensure_directories",
    "find_date_in_name",
    "list_zip_days",
    "load_previous_newsletter",
    "read_zip_texts",
    "read_zip_texts_and_media",
    "select_recent_archives",
    "_anonymize_transcript_line",
    "_format_transcript_section_header",
    "_load_prompt",
    "_prepare_transcripts",
    "_prepare_transcripts_sample",
]
