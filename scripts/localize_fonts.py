import httpx
import re
import os
from pathlib import Path

# Config
CSS_URL = "https://fonts.googleapis.com/css2?family=Outfit:wght@400;700;800&family=Inter:wght@300;400;500;600;700&display=swap"
OUTPUT_DIR = Path("src/egregora/rendering/templates/site/overrides/assets/fonts")
CSS_PATH_PREFIX = "../assets/fonts/"

# Ensure output dir exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Headers to get woff2
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

print(f"Fetching CSS from {CSS_URL}...")
response = httpx.get(CSS_URL, headers=HEADERS)
response.raise_for_status()
css_content = response.text

# Regex to parse @font-face blocks
# Captures: font-family, font-style, font-weight, src url
font_face_pattern = re.compile(r"@font-face\s*\{(.*?)\}", re.DOTALL)
property_pattern = re.compile(r"(font-family|font-style|font-weight|src):\s*([^;]+);")
url_pattern = re.compile(r"url\((.*?)\)")

font_faces = []

new_css = "/* Localized Fonts - Auto-generated */\n"

for match in font_face_pattern.finditer(css_content):
    block = match.group(1)
    props = {}
    for prop_match in property_pattern.finditer(block):
        key = prop_match.group(1).strip()
        value = prop_match.group(2).strip()
        props[key] = value

    if "src" in props:
        url_match = url_pattern.search(props["src"])
        if url_match:
            url = url_match.group(1).strip("'\"")

            # Clean family name
            family = props.get("font-family", "unknown").replace("'", "").replace('"', "").replace(" ", "")
            style = props.get("font-style", "normal")
            weight = props.get("font-weight", "400")

            # Handle subset in filename if we want uniqueness, but for now simple overwrite for same weight/style is fine
            # Actually Google Fonts sends multiple blocks for different subsets (latin, latin-ext).
            # We should preserve them. I'll append a hash or subset name if I can parse it.
            # But the 'src' URL usually is unique. I can use the filename from the URL or just increment.
            # Simpler: include unicode-range in the uniqueness check?
            # Or just name it by unicode subset?
            # Google Fonts CSS usually has comments /* latin */ before the block.

            # Let's try to extract the subset comment immediately preceding the @font-face
            # But regex matching backwards is hard.
            # I'll just use the block index to ensure uniqueness if needed, or better,
            # just use family-style-weight-subset.
            # Since I can't easily detect subset from just the block without looking at comments (which are outside),
            # I will trust that overwriting is BAD if they are different subsets.
            # Wait, different subsets have the SAME weight/style.
            # So I MUST distinct them.
            # I will use a simple counter for uniqueness or hash of the URL.

            filename_suffix = abs(hash(url)) % 10000
            filename = f"{family}-{style}-{weight}-{filename_suffix}.woff2"

            filepath = OUTPUT_DIR / filename

            print(f"Downloading {filename} from {url}...")
            font_response = httpx.get(url, headers=HEADERS)
            font_response.raise_for_status()

            with open(filepath, "wb") as f:
                f.write(font_response.content)

            # Reconstruct @font-face block
            new_block = "@font-face {\n"
            new_block += f"  font-family: '{props.get('font-family', 'unknown').replace('\'', '').replace('\"', '')}';\n"
            new_block += f"  font-style: {style};\n"
            new_block += f"  font-weight: {weight};\n"
            new_block += f"  font-display: swap;\n"
            new_block += f"  src: url('{CSS_PATH_PREFIX}{filename}') format('woff2');\n"

            unicode_range_match = re.search(r"unicode-range:\s*([^;]+);", block)
            if unicode_range_match:
                new_block += f"  unicode-range: {unicode_range_match.group(1)};\n"
            new_block += "}\n"

            new_css += new_block

print("\n--- Generated CSS ---")
# print(new_css) # Too long
with open("generated_fonts.css", "w") as f:
    f.write(new_css)
print("Saved to generated_fonts.css")
