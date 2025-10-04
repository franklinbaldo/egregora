"""WhatsApp chat parser that converts ZIP exports to pandas DataFrames."""

import logging
import re
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

from .date_utils import parse_flexible_date
from .models import WhatsAppExport

logger = logging.getLogger(__name__)


def parse_export(export: WhatsAppExport) -> pd.DataFrame:
    """
    Parse an export to DataFrame.
    
    Returns:
        DataFrame with columns: timestamp, date, time, author, message,
                               group_slug, group_name, original_line
    """
    
    # Read content
    with zipfile.ZipFile(export.zip_path) as zf:
        with zf.open(export.chat_file) as f:
            content = f.read().decode('utf-8', errors='ignore')
    
    # Parse messages
    rows = _parse_messages(content, export)
    
    if not rows:
        logger.warning(f"No messages found in {export.zip_path}")
        return pd.DataFrame()
    
    # Create DataFrame
    df = pd.DataFrame(rows)
    
    # Convert types
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = pd.to_datetime(df['date']).dt.date
    
    return df


def parse_multiple(exports: list[WhatsAppExport]) -> pd.DataFrame:
    """
    Parse multiple exports and concatenate ordered by timestamp.
    """
    
    dfs = []
    
    for export in exports:
        df = parse_export(export)
        if not df.empty:
            dfs.append(df)
    
    if not dfs:
        return pd.DataFrame()
    
    # Concatenate and sort by timestamp
    merged = pd.concat(dfs, ignore_index=True)
    merged = merged.sort_values('timestamp').reset_index(drop=True)
    
    return merged


def _parse_messages(content: str, export: WhatsAppExport) -> list[dict]:
    """Parse messages from content."""
    
    # WhatsApp patterns (with/without date on line)
    # With date: "01/10/2025, 10:30 - Author: Message"
    # Without date: "10:30 - Author: Message"
    
    pattern = re.compile(
        r'^(?:'
        r'(?P<date>\d{1,2}/\d{1,2}/\d{2,4})'
        r'(?:,\s*|\s+)'
        r')?'
        r'(?P<time>\d{1,2}:\d{2})'
        r'(?:\s*(?P<ampm>[APap][Mm]))?'
        r'\s*[—\-]\s*'
        r'(?P<author>[^:]+?):\s*'
        r'(?P<message>.+)$',
        re.MULTILINE
    )
    
    rows = []
    current_date = export.export_date
    
    for line in content.split('\n'):
        line = line.strip().replace('\u202f', ' ')
        if not line:
            continue

        match = pattern.match(line)
        if not match:
            continue

        date_str = match.group('date')
        time_str = match.group('time')
        am_pm = match.group('ampm')
        author = match.group('author')
        message = match.group('message')
        
        # Determine date
        if date_str:
            parsed_date = parse_flexible_date(date_str)
            if parsed_date:
                msg_date = parsed_date
                current_date = msg_date  # Update current date for subsequent messages
            else:
                msg_date = current_date
        else:
            msg_date = current_date

        # Parse time
        try:
            if am_pm:
                msg_time = datetime.strptime(f"{time_str} {am_pm.upper()}", "%I:%M %p").time()
            else:
                msg_time = datetime.strptime(time_str, "%H:%M").time()
            timestamp = datetime.combine(msg_date, msg_time)
        except ValueError:
            logger.debug(f"Failed to parse time '{time_str}' in line: {line}")
            continue
        
        # Skip system messages
        if _is_system_message(author.strip(), message.strip()):
            continue
        
        rows.append({
            'timestamp': timestamp,
            'date': msg_date,
            'time': msg_time.strftime("%H:%M"),
            'author': author.strip(),
            'message': message.strip(),
            'group_slug': export.group_slug,
            'group_name': export.group_name,
            'original_line': line,
        })
    
    return rows


def _is_system_message(author: str, message: str) -> bool:
    """Check if this is a WhatsApp system message to skip."""
    
    # Common system message patterns
    system_patterns = [
        r'mudou o assunto do grupo',
        r'changed the group subject',
        r'cambió el asunto del grupo',
        r'adicionou\(ou\)',
        r'added you',
        r'te agregó',
        r'saiu',
        r'left',
        r'salió',
        r'criou o grupo',
        r'created group',
        r'creó el grupo',
        r'As mensagens e chamadas',
        r'Messages and calls',
        r'Los mensajes y las llamadas',
        r'criptografia de ponta a ponta',
        r'end-to-end encrypted',
        r'cifrado de extremo a extremo',
    ]
    
    combined_text = f"{author} {message}".lower()
    
    for pattern in system_patterns:
        if re.search(pattern, combined_text, re.IGNORECASE):
            return True
    
    return False
