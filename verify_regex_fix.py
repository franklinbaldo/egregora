
import re

# Original regex
markdown_re_orig = re.compile(r"!\[[^\]]*\]\([^)]*?([^/)]+\.\w+)\)")

# Proposed regex (matches ![...] and [...])
markdown_re_new = re.compile(r"(?:!\[|\[)[^\]]*\]\([^)]*?([^/)]+\.\w+)\)")

# Test cases
text_image = "![Image](media/images/img-123.jpg)"
text_video = "[Video](media/videos/vid-123.mp4)"
text_link = "[Link](http://example.com/foo.html)"

print(f"Original on Image: {markdown_re_orig.findall(text_image)}")
print(f"Original on Video: {markdown_re_orig.findall(text_video)}")

print(f"New on Image: {markdown_re_new.findall(text_image)}")
print(f"New on Video: {markdown_re_new.findall(text_video)}")
print(f"New on Link: {markdown_re_new.findall(text_link)}")
