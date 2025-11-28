import re

# Original regex
markdown_re_orig = re.compile(r"!\[[^\]]*\]\([^)]*?([^/)]+\.\w+)\)")

# Proposed regex (matches ![...] and [...])
markdown_re_new = re.compile(r"(?:!\[|\[)[^\]]*\]\([^)]*?([^/)]+\.\w+)\)")

# Test cases
text_image = "![Image](media/images/img-123.jpg)"
text_video = "[Video](media/videos/vid-123.mp4)"
text_link = "[Link](http://example.com/foo.html)"
