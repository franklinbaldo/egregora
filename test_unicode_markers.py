"""Test unicode marker detection improvements"""
import re

# Test media detection with unicode marker
WA_MEDIA_PATTERN = re.compile(r"\b((?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)\b")

test_text_media = "28/10/2025 14:10 - Franklin: \u200eIMG-20251028-WA0035.jpg (arquivo anexado)"
print(f"Media test text: {repr(test_text_media)}")

# Pattern 1: WhatsApp filename pattern
wa_matches = WA_MEDIA_PATTERN.findall(test_text_media)
print(f"WA pattern matches: {wa_matches}")

# Pattern 2: Unicode marker pattern
unicode_pattern = r"\u200e((?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)"
unicode_matches = re.findall(unicode_pattern, test_text_media, re.IGNORECASE)
print(f"Unicode pattern matches: {unicode_matches}")

print("\n" + "="*60 + "\n")

# Test mention detection with unicode markers
WA_MENTION_PATTERN = re.compile(r"@\u2068([^\u2069]+)\u2069")

test_text_mention = "28/10/2025 14:15 - Franklin: @\u2068Eurico Max\u2069 teste de menção"
print(f"Mention test text: {repr(test_text_mention)}")

mention_matches = WA_MENTION_PATTERN.findall(test_text_mention)
print(f"Mention matches: {mention_matches}")

# Show how to extract and anonymize
if mention_matches:
    for name in mention_matches:
        print(f"  Found mention of: '{name}'")
        # This name can now be passed to anonymization
