
import re
from egregora.ops.media import find_media_references, WA_MEDIA_PATTERN

text = "[Video](VID-20250302-WA0034.mp4)"
print(f"Text: {text}")

# Test WA_MEDIA_PATTERN directly
match = WA_MEDIA_PATTERN.search(text)
print(f"Direct Regex Match: {match.group(1) if match else 'None'}")

# Test find_media_references
refs = find_media_references(text)
print(f"Found refs: {refs}")

# Test markdown_re from enricher.py
markdown_re = re.compile(r"!\[[^\]]*\]\([^)]*?([^/)]+\.\w+)\)")
md_refs = markdown_re.findall(text)
print(f"Markdown Regex Match: {md_refs}")
