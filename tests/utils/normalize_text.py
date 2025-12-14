import re

def normalize_text(text: str) -> str:
    """Normalize text for consistent snapshots.

    - Replaces timestamps
    - Normalizes line endings
    - Strips whitespace
    """
    if not text:
        return ""

    # Normalize line endings
    text = text.replace("\r\n", "\n")

    # Normalize timestamps (YYYY-MM-DD)
    # This is a broad regex, tune as needed
    text = re.sub(r"\d{4}-\d{2}-\d{2}", "YYYY-MM-DD", text)

    # Normalize times (HH:MM:SS)
    text = re.sub(r"\d{2}:\d{2}:\d{2}", "HH:MM:SS", text)

    # Strip trailing whitespace from lines
    lines = [line.rstrip() for line in text.splitlines()]

    return "\n".join(lines).strip()
