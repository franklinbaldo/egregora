"""Simple enrichment saver that creates individual markdown files."""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from .enrichment import _cache_key_for_url


def get_enrichment_uuid(url: str | None, media_key: str | None) -> str:
    """Generate UUID for enrichment file."""
    if media_key:
        return media_key
    elif url:
        return _cache_key_for_url(url)
    else:
        # Fallback
        return str(uuid.uuid4())


def save_enrichment_markdown(
    enrichment_text: str,
    url: str | None,
    media_key: str | None,
    media_path: Path | None,
    media_dir: Path,
    sender: str | None = None,
    timestamp: str | None = None,
    date_str: str | None = None,
    message: str | None = None,
) -> Path:
    """Save enrichment as markdown file with UUID name."""
    
    enrichment_uuid = get_enrichment_uuid(url, media_key)
    markdown_path = media_dir / f"{enrichment_uuid}.md"
    
    # Build markdown content
    lines = []
    
    # Header with metadata
    if url:
        lines.append(f"# Enriquecimento: {url}")
    elif media_key:
        lines.append(f"# Enriquecimento: Mídia {media_key[:8]}...")
    else:
        lines.append("# Enriquecimento")
    
    lines.append("")
    lines.append("## Metadados")
    lines.append("")
    
    if date_str:
        lines.append(f"- **Data:** {date_str}")
    if timestamp:
        lines.append(f"- **Horário:** {timestamp}")
    if sender:
        lines.append(f"- **Remetente:** {sender}")
    if url:
        lines.append(f"- **URL:** {url}")
    if media_key:
        lines.append(f"- **Mídia ID:** `{media_key}`")
        
        # Add link to local media if available
        if media_path and media_path.exists():
            # Create relative path from media/ to media file
            try:
                rel_path = media_path.relative_to(media_dir)
                lines.append(f"- **Arquivo local:** [{media_path.name}]({rel_path})")
            except ValueError:
                # If paths are not relative, try just the name
                lines.append(f"- **Arquivo local:** [{media_path.name}]({media_path.name})")
    
    lines.append("")
    
    # Original message if available
    if message:
        lines.append("## Mensagem Original")
        lines.append("")
        lines.append(f"> {message}")
        lines.append("")
    
    # Enrichment content
    lines.append("## Análise")
    lines.append("")
    lines.append(enrichment_text.strip())
    lines.append("")
    
    # Footer
    lines.append("---")
    lines.append(f"*Gerado automaticamente em {datetime.now(UTC).isoformat()}*")
    
    markdown_content = "\n".join(lines)
    
    # Ensure media directory exists
    media_dir.mkdir(parents=True, exist_ok=True)
    
    # Write markdown file
    markdown_path.write_text(markdown_content, encoding="utf-8")
    
    return markdown_path