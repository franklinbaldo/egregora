"""Auto-discovery of WhatsApp groups from ZIP files."""

from pathlib import Path
from datetime import date, datetime
from collections import defaultdict
import re
import zipfile
import unicodedata
import logging

from .models import WhatsAppExport

logger = logging.getLogger(__name__)


def discover_groups(zips_dir: Path) -> dict[str, list[WhatsAppExport]]:
    """
    Scan ZIP files and return discovered groups.
    
    Returns:
        {slug: [exports]} ordered by date
    """
    
    groups = defaultdict(list)
    
    for zip_path in sorted(zips_dir.glob("*.zip")):
        try:
            export = _extract_metadata(zip_path)
            groups[export.group_slug].append(export)
            logger.debug(f"Discovered export for {export.group_name} ({export.group_slug})")
        except Exception as e:
            logger.warning(f"Skipping {zip_path.name}: {e}")
            continue
    
    # Sort exports by date
    for slug in groups:
        groups[slug].sort(key=lambda e: e.export_date)
    
    return dict(groups)


def _extract_metadata(zip_path: Path) -> WhatsAppExport:
    """Extract metadata from a ZIP file."""
    
    with zipfile.ZipFile(zip_path) as zf:
        # Find .txt file
        txt_files = [
            f for f in zf.namelist() 
            if f.endswith('.txt') and not f.startswith('__MACOSX')
        ]
        
        if not txt_files:
            raise ValueError("No chat file found")
        
        chat_file = txt_files[0]
        
        # Extract group name
        group_name = _extract_group_name(chat_file)
        group_slug = _slugify(group_name)
        
        # Extract date
        export_date = _extract_date(zip_path, zf, chat_file)
        
        # List media files
        media_files = [f for f in zf.namelist() if f != chat_file and not f.startswith('__MACOSX')]
        
        return WhatsAppExport(
            zip_path=zip_path,
            group_name=group_name,
            group_slug=group_slug,
            export_date=export_date,
            chat_file=chat_file,
            media_files=media_files,
        )


def _extract_group_name(filename: str) -> str:
    """
    Extract group name from internal .txt file.
    Supports PT, EN, ES.
    """
    
    patterns = [
        r'Conversa do WhatsApp com (.+?)\.txt',      # PT
        r'WhatsApp Chat with (.+?)\.txt',            # EN
        r'Chat de WhatsApp con (.+?)\.txt',          # ES
        r'Conversación de WhatsApp con (.+?)\.txt',  # ES alt
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Fallback
    return filename.replace('.txt', '').strip()


def _slugify(text: str) -> str:
    """Convert to filesystem-safe slug."""
    
    # Remove accents
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    # Lowercase, remove special chars, replace spaces
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    
    return text.strip('-')


def _extract_date(zip_path: Path, zf: zipfile.ZipFile, chat_file: str) -> date:
    """Extract date from export (ZIP name > content > mtime)."""
    
    # 1. From ZIP name
    match = re.search(r'(\d{4}-\d{2}-\d{2})', zip_path.name)
    if match:
        return date.fromisoformat(match.group(1))
    
    # 2. From first message
    try:
        with zf.open(chat_file) as f:
            for _ in range(20):  # First 20 lines
                line = f.readline().decode('utf-8', errors='ignore')
                if not line:
                    break
                match = re.search(r'(\d{2})/(\d{2})/(\d{4}|\d{2})', line)
                if match:
                    day, month, year = match.groups()
                    year = int(year)
                    if year < 100:
                        year += 2000
                    return date(year, int(month), int(day))
    except Exception:
        pass
    
    # 3. Fallback: mtime of file
    timestamp = zip_path.stat().st_mtime
    return datetime.fromtimestamp(timestamp).date()