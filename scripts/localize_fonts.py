import os
import re
import requests
from pathlib import Path

# Configuration
FONTS_URL = "https://fonts.googleapis.com/css2?family=Outfit:wght@400;700;800&family=Inter:wght@300;400;500;600;700&display=swap"
BASE_DIR = Path("src/egregora/rendering/templates/site/overrides")
FONTS_DIR = BASE_DIR / "assets/fonts"
CSS_DIR = BASE_DIR / "stylesheets"
CSS_FILE = CSS_DIR / "fonts.css"

def download_fonts():
    # Ensure directories exist
    if not BASE_DIR.exists():
        print(f"Base directory {BASE_DIR} does not exist. Are you running from repo root?")
        return

    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    CSS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching CSS from {FONTS_URL}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(FONTS_URL, headers=headers)
    response.raise_for_status()
    css_content = response.text

    # Regex to find font URLs, handling optional quotes
    url_pattern = re.compile(r"url\(['\"]?(https://[^)'\"]+)['\"]?\)")

    new_css_content = css_content
    downloaded_files = set()

    unique_urls = set(url_pattern.findall(css_content))

    print(f"Found {len(unique_urls)} font files to download.")

    for font_url in unique_urls:
        filename = font_url.split("/")[-1]
        local_path = FONTS_DIR / filename

        # Download if not already downloaded
        if filename not in downloaded_files:
            print(f"Downloading {filename}...")
            font_response = requests.get(font_url)
            font_response.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(font_response.content)
            downloaded_files.add(filename)

        # Calculate relative path from CSS file to font file
        # CSS: overrides/stylesheets/fonts.css
        # Font: overrides/assets/fonts/filename
        relative_path = f"../assets/fonts/{filename}"

        # Replace URL in CSS content
        # We replace the exact URL string found by regex
        new_css_content = new_css_content.replace(font_url, relative_path)

    print(f"Saving CSS to {CSS_FILE}...")
    with open(CSS_FILE, "w") as f:
        f.write(new_css_content)

    print("Done.")

if __name__ == "__main__":
    download_fonts()
