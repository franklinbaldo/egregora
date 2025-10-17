"""Simple enrichment using just the basic Gemini approach."""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

try:
    from google import genai
    from google.genai import types
except ModuleNotFoundError:
    genai = None
    types = None

from .enrichment import _cache_key_for_url

logger = logging.getLogger(__name__)


def get_mimetype_subfolder(media_path: Path, media_type: str) -> str:
    """Get the appropriate subfolder name based on mimetype."""
    if media_type == "image" or media_path.suffix.lower() in [
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
    ]:
        return "images"
    elif media_type == "video" or media_path.suffix.lower() in [".mp4", ".webm", ".ogg", ".mov"]:
        return "videos"
    elif media_type == "audio" or media_path.suffix.lower() in [
        ".mp3",
        ".wav",
        ".ogg",
        ".m4a",
        ".opus",
    ]:
        return "audio"
    elif media_path.suffix.lower() in [
        ".pdf",
        ".docx",
        ".doc",
        ".txt",
        ".rtf",
        ".odt",
        ".pptx",
        ".ppt",
        ".xlsx",
        ".xls",
    ]:
        return "documents"
    else:
        return "files"


SIMPLE_ENRICHMENT_PROMPT = """You are a **Multimodal Context Analyst** for the **Egregora System**.

The content may originate from a conversation, article, video, or other media type.

---

## Summary

(In 2–3 sentences, objectively describe the main content and its relevance.
Use clear, analytical, and factual language — avoid personal opinions or embellishment.)

---

## Context

(Explain the background and circumstances:

* Where the content comes from — e.g., article, link, video, image
* Why it is relevant or noteworthy
* The central topic and the audience potentially affected)

---

## Key Takeaways

(List 3–5 concise, factual points summarizing what was observed or learned.
Each bullet should represent a self-contained, explanatory idea.)

*
*
*
*
*

---

## Metadata

(Technical or contextual information about the page or content —
e.g., title, author, date, source link, tags, media type, etc.)
"""


def get_enrichment_uuid(url: str | None, media_key: str | None) -> str:
    """Generate UUID for enrichment file."""
    if media_key:
        return media_key
    elif url:
        return _cache_key_for_url(url)
    else:
        # Fallback
        return str(uuid.uuid4())


async def simple_enrich_url_with_cache(url: str, context_message: str = "", cache=None) -> str:
    """Simple enrichment of a URL with caching support."""

    # Check cache first
    if cache is not None:
        try:
            cache_key = _cache_key_for_url(url)
            cached_result = cache.get(cache_key)
            if cached_result and isinstance(cached_result, dict):
                cached_text = cached_result.get("enrichment_text")
                if cached_text:
                    logger.info(f"    💾 Cache hit for {url}")
                    return cached_text
        except Exception:
            pass  # Cache errors shouldn't break enrichment

    # Perform enrichment
    result = await simple_enrich_url(url, context_message)

    # Store in cache
    if cache is not None and result and not result.startswith("❌"):
        try:
            cache_key = _cache_key_for_url(url)
            cache_entry = {
                "enrichment_text": result,
                "url": url,
                "timestamp": datetime.now().isoformat(),
            }
            cache.set(cache_key, cache_entry)
        except Exception:
            pass  # Cache errors shouldn't break enrichment

    return result


async def simple_enrich_url(url: str, context_message: str = "") -> str:
    """Simple enrichment of a URL using basic Gemini approach."""
    if genai is None or types is None:
        return "❌ Google GenAI not available"

    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

        # Replace INSERT_INPUT_HERE with the actual URL
        input_text = url
        if context_message:
            input_text += f"\n\nContext from conversation: {context_message}"

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=input_text),
                ],
            ),
        ]

        tools = [
            types.Tool(url_context=types.UrlContext()),
        ]

        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_budget=-1,
            ),
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_HARASSMENT",
                    threshold="BLOCK_NONE",
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH",
                    threshold="BLOCK_NONE",
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    threshold="BLOCK_NONE",
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_NONE",
                ),
            ],
            tools=tools,
            system_instruction=[
                types.Part.from_text(text=SIMPLE_ENRICHMENT_PROMPT),
            ],
        )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-flash-latest",
            contents=contents,
            config=generate_content_config,
        )

        return response.text or "❌ Empty response"

    except Exception as exc:
        logger.warning("Failed to enrich URL %s: %s", url, exc)
        return f"❌ Error: {exc}"


def save_simple_enrichment(
    url: str,
    enrichment_text: str,
    media_dir: Path,
    sender: str | None = None,
    timestamp: str | None = None,
    date_str: str | None = None,
    message: str | None = None,
    media_path: Path | None = None,
    media_type: str | None = None,
) -> Path:
    """Save simple enrichment as markdown file."""

    # URL enrichments go in a 'urls' subfolder
    urls_dir = media_dir / "urls"
    urls_dir.mkdir(parents=True, exist_ok=True)

    enrichment_uuid = get_enrichment_uuid(url, None)
    markdown_path = urls_dir / f"{enrichment_uuid}.md"

    # Build markdown content
    lines = []

    lines.append(f"# Enriquecimento: {url}")
    lines.append("")
    lines.append("## Metadados")
    lines.append("")

    if date_str:
        lines.append(f"- **Data:** {date_str}")
    if timestamp:
        lines.append(f"- **Horário:** {timestamp}")
    if sender:
        lines.append(f"- **Remetente:** {sender}")
    lines.append(f"- **URL:** {url}")

    lines.append("")

    # Original message if available
    if message:
        lines.append("## Mensagem Original")
        lines.append("")
        lines.append(f"> {message}")
        lines.append("")

    # Media embed section
    lines.append("## Conteúdo")
    lines.append("")

    # Add iframe for URL
    if url:
        lines.append("### URL Original")
        lines.append("")
        lines.append(
            f'<iframe src="{url}" width="100%" height="500" frameborder="0" loading="lazy"></iframe>'
        )
        lines.append("")
        lines.append(f"[Abrir em nova aba]({url})")
        lines.append("")

    # Add local media embed if available
    if media_path and media_path.exists():
        lines.append("### Mídia Local")
        lines.append("")

        # Get relative path from markdown file to media file
        try:
            # Both files are in media/ directory, so just use filename
            media_filename = media_path.name

            # Determine media type and create appropriate embed
            if media_type == "image" or (
                media_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"]
            ):
                lines.append(f"![Mídia local]({media_filename})")
            elif media_type == "video" or (
                media_path.suffix.lower() in [".mp4", ".webm", ".ogg", ".mov"]
            ):
                lines.append('<video controls width="100%">')
                lines.append(
                    f'  <source src="{media_filename}" type="video/{media_path.suffix[1:]}">'
                )
                lines.append("  Seu navegador não suporta o elemento de vídeo.")
                lines.append("</video>")
            elif media_type == "audio" or (
                media_path.suffix.lower() in [".mp3", ".wav", ".ogg", ".m4a"]
            ):
                lines.append("<audio controls>")
                lines.append(
                    f'  <source src="{media_filename}" type="audio/{media_path.suffix[1:]}">'
                )
                lines.append("  Seu navegador não suporta o elemento de áudio.")
                lines.append("</audio>")
            else:
                # Generic file download link
                lines.append(f"[📁 Download: {media_filename}]({media_filename})")

            lines.append("")
        except Exception:
            lines.append(f"[📁 Arquivo local: {media_path.name}]({media_path.name})")
            lines.append("")

    # Enrichment content
    lines.append("## Análise")
    lines.append("")
    lines.append(enrichment_text.strip())
    lines.append("")

    markdown_content = "\n".join(lines)

    # Ensure media directory exists
    media_dir.mkdir(parents=True, exist_ok=True)

    # Write markdown file
    markdown_path.write_text(markdown_content, encoding="utf-8")

    return markdown_path


async def simple_enrich_media_with_cache(
    media_path: Path, media_type: str, context_message: str = "", cache=None
) -> str:
    """Simple enrichment of local media using basic Gemini approach."""

    # Check cache first (using media path as key for local media)
    if cache is not None:
        try:
            # Use media filename as cache key for local media
            cache_key = str(media_path.name)
            cached_result = cache.get(cache_key)
            if cached_result and isinstance(cached_result, dict):
                cached_text = cached_result.get("enrichment_text")
                if cached_text:
                    logger.info(f"    💾 Cache hit for media {media_path.name}")
                    return cached_text
        except Exception:
            pass  # Cache errors shouldn't break enrichment

    # Perform enrichment with media
    result = await simple_enrich_media(media_path, media_type, context_message)

    # Store in cache
    if cache is not None and result and not result.startswith("❌"):
        try:
            cache_key = str(media_path.name)
            cache_entry = {
                "enrichment_text": result,
                "media_path": str(media_path),
                "media_type": media_type,
                "timestamp": datetime.now().isoformat(),
            }
            cache.set(cache_key, cache_entry)
        except Exception:
            pass  # Cache errors shouldn't break enrichment

    return result


async def simple_enrich_media(media_path: Path, media_type: str, context_message: str = "") -> str:
    """Simple enrichment of local media using basic Gemini approach."""
    if genai is None or types is None:
        return "❌ Google GenAI not available"

    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

        # Just send the media file to Gemini
        parts = []

        if media_path.exists():
            try:
                media_bytes = media_path.read_bytes()
                # Simple MIME type detection
                suffix = media_path.suffix.lower()
                if suffix == ".jpg":
                    mime_type = "image/jpeg"
                elif suffix == ".jpeg":
                    mime_type = "image/jpeg"
                elif suffix == ".png":
                    mime_type = "image/png"
                elif suffix == ".gif":
                    mime_type = "image/gif"
                elif suffix == ".webp":
                    mime_type = "image/webp"
                elif suffix == ".mp4":
                    mime_type = "video/mp4"
                elif suffix == ".webm":
                    mime_type = "video/webm"
                elif suffix == ".mov":
                    mime_type = "video/quicktime"
                elif suffix == ".pdf":
                    mime_type = "application/pdf"
                elif suffix == ".docx":
                    mime_type = (
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                elif suffix == ".doc":
                    mime_type = "application/msword"
                elif suffix == ".txt":
                    mime_type = "text/plain"
                elif suffix == ".rtf":
                    mime_type = "application/rtf"
                elif suffix == ".odt":
                    mime_type = "application/vnd.oasis.opendocument.text"
                elif suffix == ".pptx":
                    mime_type = (
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
                elif suffix == ".ppt":
                    mime_type = "application/vnd.ms-powerpoint"
                elif suffix == ".xlsx":
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                elif suffix == ".xls":
                    mime_type = "application/vnd.ms-excel"
                else:
                    # Skip unsupported media
                    return f"❌ Unsupported media type: {suffix}"

                parts.append(types.Part.from_bytes(data=media_bytes, mime_type=mime_type))

            except Exception as exc:
                logger.warning(f"Failed to read media file {media_path}: {exc}")
                return f"❌ Error reading file: {exc}"
        else:
            return "❌ Media file not found"

        # Add context if available
        if context_message:
            parts.insert(0, types.Part.from_text(text=f"Context: {context_message}"))

        contents = [types.Content(role="user", parts=parts)]

        config = types.GenerateContentConfig(
            system_instruction=[types.Part.from_text(text=SIMPLE_ENRICHMENT_PROMPT)],
        )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-flash-latest",
            contents=contents,
            config=config,
        )

        return response.text or "❌ Empty response"

    except Exception as exc:
        logger.warning("Failed to enrich media %s: %s", media_path, exc)
        return f"❌ Error: {exc}"


def save_media_enrichment(
    media_key: str,
    media_path: Path,
    media_type: str,
    enrichment_text: str,
    media_dir: Path,
    sender: str | None = None,
    timestamp: str | None = None,
    date_str: str | None = None,
    message: str | None = None,
) -> Path:
    """Save enrichment for local media file."""

    # Organize into subfolder by mimetype
    subfolder = get_mimetype_subfolder(media_path, media_type)
    subfolder_path = media_dir / subfolder
    subfolder_path.mkdir(parents=True, exist_ok=True)

    markdown_path = subfolder_path / f"{media_key}.md"

    # Build markdown content
    lines = []

    lines.append(f"# Enriquecimento: Mídia {media_key[:8]}...")
    lines.append("")
    lines.append("## Metadados")
    lines.append("")

    if date_str:
        lines.append(f"- **Data:** {date_str}")
    if timestamp:
        lines.append(f"- **Horário:** {timestamp}")
    if sender:
        lines.append(f"- **Remetente:** {sender}")
    lines.append(f"- **Mídia ID:** `{media_key}`")
    lines.append(f"- **Tipo:** {media_type}")
    if media_path.exists():
        lines.append(f"- **Arquivo:** {media_path.name}")
        lines.append(f"- **Tamanho:** {media_path.stat().st_size} bytes")

    lines.append("")

    # Original message if available
    if message:
        lines.append("## Mensagem Original")
        lines.append("")
        lines.append(f"> {message}")
        lines.append("")

    # Media embed section
    lines.append("## Conteúdo")
    lines.append("")

    if media_path.exists():
        media_filename = media_path.name

        # Create relative path from current subfolder to media file
        # The media file should be in the same subfolder as the markdown

        # Determine media type and create appropriate embed
        if media_type == "image" or (
            media_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"]
        ):
            lines.append(f"![{media_path.name}]({media_filename})")
        elif media_type == "video" or (
            media_path.suffix.lower() in [".mp4", ".webm", ".ogg", ".mov"]
        ):
            lines.append('<video controls width="100%">')
            lines.append(f'  <source src="{media_filename}" type="video/{media_path.suffix[1:]}">')
            lines.append("  Seu navegador não suporta o elemento de vídeo.")
            lines.append("</video>")
        elif media_type == "audio" or (
            media_path.suffix.lower() in [".mp3", ".wav", ".ogg", ".m4a", ".opus"]
        ):
            lines.append("<audio controls>")
            lines.append(f'  <source src="{media_filename}" type="audio/{media_path.suffix[1:]}">')
            lines.append("  Seu navegador não suporta o elemento de áudio.")
            lines.append("</audio>")
        elif media_path.suffix.lower() == ".pdf":
            lines.append(
                f'<embed src="{media_filename}" type="application/pdf" width="100%" height="600px" />'
            )
            lines.append(f'<p><a href="{media_filename}">📄 Abrir PDF em nova aba</a></p>')
        elif media_path.suffix.lower() in [
            ".docx",
            ".doc",
            ".txt",
            ".rtf",
            ".odt",
            ".pptx",
            ".ppt",
            ".xlsx",
            ".xls",
        ]:
            # Document types - provide download link with appropriate icon
            doc_icons = {
                ".docx": "📝",
                ".doc": "📝",
                ".txt": "📄",
                ".rtf": "📝",
                ".odt": "📝",
                ".pptx": "📊",
                ".ppt": "📊",
                ".xlsx": "📊",
                ".xls": "📊",
            }
            icon = doc_icons.get(media_path.suffix.lower(), "📁")
            lines.append(f'<p><a href="{media_filename}">{icon} {media_filename}</a></p>')
            lines.append(
                "<p><em>Clique no link acima para baixar e visualizar o documento.</em></p>"
            )
        else:
            # Generic file download link
            lines.append(f"[📁 Download: {media_filename}]({media_filename})")

        lines.append("")
    else:
        lines.append("⚠️ Arquivo de mídia não encontrado")
        lines.append("")

    # Enrichment content
    lines.append("## Análise")
    lines.append("")
    lines.append(enrichment_text.strip())
    lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"*Gerado automaticamente em {datetime.now().isoformat()}*")

    markdown_content = "\n".join(lines)

    # Ensure media directory exists
    media_dir.mkdir(parents=True, exist_ok=True)

    # Write markdown file
    markdown_path.write_text(markdown_content, encoding="utf-8")

    return markdown_path
