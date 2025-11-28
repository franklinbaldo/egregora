"""Test unicode marker detection improvements."""

import re

# Test media detection with unicode marker
WA_MEDIA_PATTERN = re.compile(r"\b((?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)\b")

test_text_media = "28/10/2025 14:10 - Franklin: \u200eIMG-20251028-WA0035.jpg (arquivo anexado)"

# Pattern 1: WhatsApp filename pattern
wa_matches = WA_MEDIA_PATTERN.findall(test_text_media)

# Pattern 2: Unicode marker pattern
unicode_pattern = r"\u200e((?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)"
unicode_matches = re.findall(unicode_pattern, test_text_media, re.IGNORECASE)


# Test mention detection with unicode markers
WA_MENTION_PATTERN = re.compile(r"@\u2068([^\u2069]+)\u2069")

test_text_mention = "28/10/2025 14:15 - Franklin: @\u2068Eurico Max\u2069 teste de menção"

mention_matches = WA_MENTION_PATTERN.findall(test_text_mention)

# Show how to extract and anonymize
if mention_matches:
    for _name in mention_matches:
        pass
        # This name can now be passed to anonymization
