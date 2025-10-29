"""Simple UUID5-based anonymization for authors and mentions.

This code is ported verbatim from Egregora v2 to ensure
byte-for-byte identical anonymization behavior.
"""

import re
import uuid

NAMESPACE_AUTHOR = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
SYSTEM_AUTHOR = "system"

MENTION_PATTERN = re.compile(r"\u2068(?P<name>.*?)\u2069")


def anonymize_author(author: str) -> str:
    """Generate deterministic UUID5 pseudonym for author."""
    normalized = author.strip().lower()
    author_uuid = uuid.uuid5(NAMESPACE_AUTHOR, normalized)
    return author_uuid.hex[:8]


def anonymize_mentions(text: str) -> str:
    """Replace WhatsApp mentions (Unicode markers) with UUID5 pseudonyms."""
    if not text or "\u2068" not in text:
        return text

    def replace_mention(match):
        name = match.group("name")
        pseudonym = anonymize_author(name)
        return pseudonym

    return MENTION_PATTERN.sub(replace_mention, text)
