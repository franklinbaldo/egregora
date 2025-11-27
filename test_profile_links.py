"""Test profile link generation for mentions"""
import re
import uuid
from egregora.privacy.uuid_namespaces import deterministic_author_uuid

WA_MENTION_PATTERN = re.compile(r"@\u2068([^\u2069]+)\u2069")

def _convert_whatsapp_mentions_to_markdown(message: str, tenant_id: str, source: str) -> str:
    """Convert WhatsApp unicode-wrapped mentions to profile wikilinks."""
    if not message:
        return message
    
    def replace_mention(match):
        """Replace a single mention with its profile link."""
        mentioned_name = match.group(1)
        # Generate deterministic UUID for this author
        author_uuid = deterministic_author_uuid(tenant_id, source, mentioned_name)
        # Return wikilink format: [[profile/uuid]]
        return f"[[profile/{author_uuid}]]"
    
    # Replace unicode-wrapped mentions with profile links
    result = WA_MENTION_PATTERN.sub(replace_mention, message)
    return result

# Test cases
tenant_id = "test-group"
source = "whatsapp"

test_cases = [
    "28/10/2025 14:15 - Franklin: @\u2068Eurico Max\u2069 teste de menção",
    "Hey @\u2068John Doe\u2069 and @\u2068Jane Smith\u2069, check this out!",
    "No mentions here",
    "@\u2068Single Person\u2069",
]

print("Testing mention to profile link conversion:\n")
for test in test_cases:
    result = _convert_whatsapp_mentions_to_markdown(test, tenant_id, source)
    print(f"Input:  {repr(test)}")
    print(f"Output: {result}")
    
    # Show the UUID for verification
    mentions = WA_MENTION_PATTERN.findall(test)
    if mentions:
        print(f"  Mentions found: {mentions}")
        for name in mentions:
            uuid_val = deterministic_author_uuid(tenant_id, source, name)
            print(f"    - '{name}' → {uuid_val}")
    print()

# Verify determinism - same name should always generate same UUID
print("\nVerifying determinism:")
name = "John Doe"
uuid1 = deterministic_author_uuid(tenant_id, source, name)
uuid2 = deterministic_author_uuid(tenant_id, source, name)
print(f"UUID for '{name}' (call 1): {uuid1}")
print(f"UUID for '{name}' (call 2): {uuid2}")
print(f"Deterministic: {uuid1 == uuid2}")
