"""Test mention conversion."""
import re

WA_MENTION_PATTERN = re.compile(r"@\u2068([^\u2069]+)\u2069")

def _convert_whatsapp_mentions_to_markdown(message: str) -> str:
    """Convert WhatsApp unicode-wrapped mentions to standard markdown."""
    if not message:
        return message
    return WA_MENTION_PATTERN.sub(r"@\1", message)

# Test cases
test_cases = [
    "28/10/2025 14:15 - Franklin: @\u2068Eurico Max\u2069 teste de menção",
    "Hey @\u2068John Doe\u2069 and @\u2068Jane Smith\u2069, check this out!",
    "No mentions here",
    "@\u2068Single Person\u2069",
]

for test in test_cases:
    result = _convert_whatsapp_mentions_to_markdown(test)
