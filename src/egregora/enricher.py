"""Simple enrichment: extract media, add LLM-described context as DataFrame rows."""

import hashlib
import re
import uuid
import zipfile
from datetime import timedelta
from pathlib import Path

import polars as pl
from google import genai
from google.genai import types as genai_types

from .config_types import EnrichmentConfig
from .genai_utils import call_with_retries
from .model_config import ModelConfig
from .prompt_templates import (
    render_media_enrichment_detailed_prompt,
    render_url_enrichment_detailed_prompt,
)

URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')

# WhatsApp attachment markers (special Unicode)
ATTACHMENT_MARKERS = (
    "(arquivo anexado)",
    "(file attached)",
    "(archivo adjunto)",
    "\u200e<attached:",  # Unicode left-to-right mark + <attached:
)

# Media type detection by extension
MEDIA_EXTENSIONS = {
    # Images
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".gif": "image",
    ".webp": "image",
    # Videos
    ".mp4": "video",
    ".mov": "video",
    ".3gp": "video",
    ".avi": "video",
    # Audio
    ".opus": "audio",
    ".ogg": "audio",
    ".mp3": "audio",
    ".m4a": "audio",
    ".aac": "audio",
    # Documents
    ".pdf": "document",
    ".doc": "document",
    ".docx": "document",
}


def get_media_subfolder(file_extension: str) -> str:
    """Get subfolder based on media type."""
    ext = file_extension.lower()
    media_type = MEDIA_EXTENSIONS.get(ext, "file")

    if media_type == "image":
        return "images"
    elif media_type == "video":
        return "videos"
    elif media_type == "audio":
        return "audio"
    elif media_type == "document":
        return "documents"
    else:
        return "files"


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from text."""
    if not text:
        return []
    return URL_PATTERN.findall(text)


def find_media_references(text: str) -> list[str]:
    """
    Find media filenames in WhatsApp messages.

    WhatsApp marks media with special patterns like:
    - "IMG-20250101-WA0001.jpg (arquivo anexado)"
    - "<attached: IMG-20250101-WA0001.jpg>"
    """
    if not text:
        return []

    media_files = []

    # Pattern 1: filename before attachment marker
    # "IMG-20250101-WA0001.jpg (file attached)"
    for marker in ATTACHMENT_MARKERS:
        pattern = r"([\w\-\.]+\.\w+)\s*" + re.escape(marker)
        matches = re.findall(pattern, text, re.IGNORECASE)
        media_files.extend(matches)

    # Pattern 2: WhatsApp standard filenames (without marker)
    # "IMG-20250101-WA0001.jpg"
    wa_pattern = r"\b((?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)\b"
    wa_matches = re.findall(wa_pattern, text)
    media_files.extend(wa_matches)

    return list(set(media_files))  # Deduplicate


def extract_media_from_zip(
    zip_path: Path,
    filenames: set[str],
    output_dir: Path,
    group_slug: str,
) -> dict[str, Path]:
    """
    Extract media files from ZIP and save to output_dir/media/.

    Returns dict mapping original filename to saved path.
    """
    if not filenames:
        return {}

    media_dir = output_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    # Create deterministic namespace for UUID generation
    namespace = uuid.uuid5(uuid.NAMESPACE_DNS, group_slug)

    extracted = {}

    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue

            filename = Path(info.filename).name

            # Check if this file is in our wanted list
            if filename not in filenames:
                continue

            # Read file content
            file_content = zf.read(info)

            # Generate deterministic UUID based on content
            content_hash = hashlib.sha256(file_content).hexdigest()
            file_uuid = uuid.uuid5(namespace, content_hash)

            # Get file extension and subfolder
            file_ext = Path(filename).suffix
            subfolder = get_media_subfolder(file_ext)

            # Create destination path
            subfolder_path = media_dir / subfolder
            subfolder_path.mkdir(parents=True, exist_ok=True)

            new_filename = f"{file_uuid}{file_ext}"
            dest_path = subfolder_path / new_filename

            # Save file if not already exists
            if not dest_path.exists():
                dest_path.write_bytes(file_content)

            extracted[filename] = dest_path

    return extracted


def replace_media_mentions(text: str, media_mapping: dict[str, Path], output_dir: Path) -> str:
    """
    Replace WhatsApp media filenames with new UUID5 paths.

    "Check this IMG-20250101-WA0001.jpg (file attached)"
    → "Check this ![Image](media/images/abc123def.jpg)"
    """
    if not text or not media_mapping:
        return text

    result = text

    for original_filename, new_path in media_mapping.items():
        # Get relative path from output_dir
        try:
            relative_path = new_path.relative_to(output_dir)
        except ValueError:
            # Fallback to name if can't get relative path
            relative_path = new_path

        # Determine if it's an image for markdown rendering
        ext = new_path.suffix.lower()
        is_image = ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]

        # Create markdown link
        if is_image:
            replacement = f"![Image]({relative_path.as_posix()})"
        else:
            replacement = f"[{new_path.name}]({relative_path.as_posix()})"

        # Replace all occurrences with any attachment marker
        for marker in ATTACHMENT_MARKERS:
            pattern = re.escape(original_filename) + r"\s*" + re.escape(marker)
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        # Also replace bare filename (without marker)
        result = re.sub(r"\b" + re.escape(original_filename) + r"\b", replacement, result)

    return result


def extract_and_replace_media(
    df: pl.DataFrame,
    zip_path: Path,
    output_dir: Path,
    group_slug: str = "shared",
) -> tuple[pl.DataFrame, dict[str, Path]]:
    """
    Extract media from ZIP and replace mentions in DataFrame.

    Returns:
        - Updated DataFrame with new media paths
        - Media mapping (original → extracted path)
    """
    # Step 1: Find all media references
    all_media = set()
    for row in df.iter_rows(named=True):
        message = row.get("message", "")
        media_refs = find_media_references(message)
        all_media.update(media_refs)

    # Step 2: Extract from ZIP
    media_mapping = extract_media_from_zip(zip_path, all_media, output_dir, group_slug)

    if not media_mapping:
        return df, {}

    # Step 3: Replace mentions in DataFrame
    def replace_in_message(message: str) -> str:
        return replace_media_mentions(message, media_mapping, output_dir)

    updated_df = df.with_columns(
        pl.col("message").map_elements(replace_in_message, return_dtype=pl.Utf8)
    )

    return updated_df, media_mapping


def detect_media_type(file_path: Path) -> str | None:
    """Detect media type from file extension."""
    ext = file_path.suffix.lower()
    for extension, media_type in MEDIA_EXTENSIONS.items():
        if ext == extension:
            return media_type
    return None


async def enrich_url(
    url: str,
    original_message: str,
    sender_uuid: str,
    timestamp,
    config: EnrichmentConfig,
) -> str:
    """
    Generate detailed enrichment for URL and save as .md file.

    Returns: Path to saved enrichment file
    """
    # Generate UUID for enrichment file
    hashlib.md5(url.encode()).hexdigest()
    enrichment_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))

    # Prepare context
    date_str = timestamp.strftime("%Y-%m-%d")
    time_str = timestamp.strftime("%H:%M")

    prompt = render_url_enrichment_detailed_prompt(
        url=url,
        original_message=original_message,
        sender_uuid=sender_uuid,
        date=date_str,
        time=time_str,
    )

    try:
        response = await call_with_retries(
            config.client.aio.models.generate_content,
            model=config.model,
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=prompt)],
                )
            ],
            config=genai_types.GenerateContentConfig(temperature=0.3),
        )

        markdown_content = (response.text or "").strip()

        # Save to media/urls/
        urls_dir = config.output_dir / "media" / "urls"
        urls_dir.mkdir(parents=True, exist_ok=True)

        enrichment_path = urls_dir / f"{enrichment_id}.md"
        enrichment_path.write_text(markdown_content, encoding="utf-8")

        return str(enrichment_path)

    except Exception as e:
        return f"[Failed to enrich URL: {str(e)}]"


async def enrich_media(
    file_path: Path,
    original_message: str,
    sender_uuid: str,
    timestamp,
    config: EnrichmentConfig,
) -> str:
    """
    Generate detailed enrichment for media file and save as .md file.

    Returns: Path to saved enrichment file
    """
    # Determine media type
    media_type = detect_media_type(file_path)
    if not media_type:
        return f"[Unknown media type: {file_path.name}]"

    # Generate UUID for enrichment file (based on file path)
    enrichment_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(file_path)))

    # Get relative path from output_dir
    try:
        media_path = file_path.relative_to(config.output_dir)
    except ValueError:
        media_path = file_path

    # Prepare context
    date_str = timestamp.strftime("%Y-%m-%d")
    time_str = timestamp.strftime("%H:%M")

    prompt = render_media_enrichment_detailed_prompt(
        media_type=media_type,
        media_filename=file_path.name,
        media_path=str(media_path),
        original_message=original_message,
        sender_uuid=sender_uuid,
        date=date_str,
        time=time_str,
    )

    try:
        # Upload file to Gemini (for vision/audio analysis)
        uploaded_file = await call_with_retries(
            config.client.aio.files.upload,
            path=str(file_path),
        )

        file_part = None
        if getattr(uploaded_file, "uri", None):
            file_part = genai_types.Part(
                file_data=genai_types.FileData(
                    file_uri=uploaded_file.uri,
                    mime_type=getattr(uploaded_file, "mime_type", None),
                    display_name=file_path.name,
                )
            )

        # Generate enrichment
        parts = [genai_types.Part(text=prompt)]
        if file_part is not None:
            parts.append(file_part)

        response = await call_with_retries(
            config.client.aio.models.generate_content,
            model=config.model,
            contents=[
                genai_types.Content(
                    role="user",
                    parts=parts,
                )
            ],
        )

        markdown_content = (response.text or "").strip()

        # Save to media/enrichments/
        enrichments_dir = config.output_dir / "media" / "enrichments"
        enrichments_dir.mkdir(parents=True, exist_ok=True)

        enrichment_path = enrichments_dir / f"{enrichment_id}.md"
        enrichment_path.write_text(markdown_content, encoding="utf-8")

        return str(enrichment_path)

    except Exception as e:
        return f"[Failed to enrich media: {str(e)}]"


async def enrich_dataframe(  # noqa: PLR0912, PLR0913
    df: pl.DataFrame,
    media_mapping: dict[str, Path],
    client: genai.Client,
    output_dir: Path,
    model_config=None,
    enable_url: bool = True,
    enable_media: bool = True,
    max_enrichments: int = 50,
) -> pl.DataFrame:
    """
    Add LLM-generated enrichment rows to DataFrame for URLs and media.

    Note: Media must already be extracted and replaced in df.
    Use extract_and_replace_media() first.

    Args:
        df: DataFrame with media paths already replaced
        media_mapping: Mapping of original filenames to extracted paths
        client: Gemini client
        model_config: Model configuration object
        enable_url: Add URL descriptions
        enable_media: Add media descriptions
        max_enrichments: Maximum enrichments to add

    Returns new DataFrame with additional rows authored by 'egregora'.
    """
    # Get model names from config
    if model_config is None:
        model_config = ModelConfig()
    url_model = model_config.get_model("enricher")
    vision_model = model_config.get_model("enricher_vision")
    if df.is_empty():
        return df

    new_rows = []
    enrichment_count = 0

    for row in df.iter_rows(named=True):
        if enrichment_count >= max_enrichments:
            break

        message = row.get("message", "")
        timestamp = row["timestamp"]
        author = row.get("author", "unknown")

        # Enrich URLs
        if enable_url:
            urls = extract_urls(message)
            for url in urls[:3]:  # Max 3 URLs per message
                if enrichment_count >= max_enrichments:
                    break

                # Generate enrichment .md file
                enrichment_config = EnrichmentConfig(
                    client=client,
                    output_dir=output_dir,
                    model=url_model,
                )
                enrichment_path = await enrich_url(
                    url=url,
                    original_message=message,
                    sender_uuid=author,
                    timestamp=timestamp,
                    config=enrichment_config,
                )

                # Add reference to DataFrame
                enrichment_timestamp = timestamp + timedelta(seconds=1)
                new_rows.append(
                    {
                        "timestamp": enrichment_timestamp,
                        "date": enrichment_timestamp.date(),
                        "author": "egregora",
                        "message": f"[URL Enrichment] {url}\nEnrichment saved: {enrichment_path}",
                        "original_line": "",
                        "tagged_line": "",
                    }
                )
                enrichment_count += 1

        # Enrich media (use the already-extracted files)
        if enable_media and media_mapping:
            # Find media files in this message (by checking the mapping values)
            for original_filename, file_path in media_mapping.items():
                # Check if this media is referenced in this message
                if original_filename in message or file_path.name in message:
                    if enrichment_count >= max_enrichments:
                        break

                    # Generate enrichment .md file
                    enrichment_config = EnrichmentConfig(
                        client=client,
                        output_dir=output_dir,
                        model=vision_model,
                    )
                    enrichment_path = await enrich_media(
                        file_path=file_path,
                        original_message=message,
                        sender_uuid=author,
                        timestamp=timestamp,
                        config=enrichment_config,
                    )

                    # Add reference to DataFrame
                    enrichment_timestamp = timestamp + timedelta(seconds=1)
                    new_rows.append(
                        {
                            "timestamp": enrichment_timestamp,
                            "date": enrichment_timestamp.date(),
                            "author": "egregora",
                            "message": f"[Media Enrichment] {file_path.name}\nEnrichment saved: {enrichment_path}",
                            "original_line": "",
                            "tagged_line": "",
                        }
                    )
                    enrichment_count += 1

    if not new_rows:
        return df

    base_row = {column: None for column in df.columns}
    normalized_rows = []
    for row in new_rows:
        normalized = base_row.copy()
        normalized.update(row)
        normalized_rows.append(normalized)

    enrichment_df = pl.DataFrame(normalized_rows, schema=df.schema, strict=False)
    combined = pl.concat([df, enrichment_df])
    combined = combined.sort("timestamp")

    return combined
