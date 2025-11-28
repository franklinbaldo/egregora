
import re

from egregora.ops.media import WA_MEDIA_PATTERN, find_media_references

text = "[Video](VID-20250302-WA0034.mp4)"

# Test WA_MEDIA_PATTERN directly
match = WA_MEDIA_PATTERN.search(text)

# Test find_media_references
refs = find_media_references(text)

# Test markdown_re from enricher.py
markdown_re = re.compile(r"!\[[^\]]*\]\([^)]*?([^/)]+\.\w+)\)")
md_refs = markdown_re.findall(text)
