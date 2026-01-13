"""Script to generate documentation assets as SVGs using Gemini Text Generation."""

import logging
import sys
import re
import time
from pathlib import Path
from typing import NamedTuple

# Ensure src is in python path
sys.path.append(str(Path(__file__).parents[1] / "src"))

from egregora.orchestration.factory import PipelineFactory

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class AssetSpec(NamedTuple):
    filename: str
    prompt: str

ASSETS = [
    AssetSpec(
        filename="favicon.svg",
        prompt=(
            "Generate the full SVG code for a minimalist, modern favicon for a project named 'Egregora'. "
            "The design should be an abstract geometric shape representing connection, emergence, and reflection. "
            "Use a color palette of Teal (#009688) and Amber (#FFC107). "
            "The SVG must be square (e.g., viewBox='0 0 512 512'). "
            "Output ONLY the SVG code, starting with <svg and ending with </svg>. No markdown formatting."
        )
    ),
    AssetSpec(
        filename="architecture_concept.svg",
        prompt=(
            "Generate the full SVG code for a conceptual diagram of the Egregora architecture. "
            "Visual metaphor: Raw chaotic text lines entering a prism/lens on the left, being organized, and emerging as structured, beautiful blocks on the right. "
            "Style: Clean, schematic, tech-minimalist. "
            "Colors: Teal (#009688), Amber (#FFC107), and Slate Gray. "
            "Size: 800x400. "
            "Output ONLY the SVG code."
        )
    ),
    AssetSpec(
        filename="social_card_bg.svg",
        prompt=(
            "Generate the full SVG code for a social media card background pattern. "
            "Design: A subtle, abstract network of nodes and edges, looking like a constellation or neural network. "
            "Colors: Dark background (#263238) with faint Teal (#009688) connections. "
            "Size: 1200x630. "
            "Output ONLY the SVG code."
        )
    ),
]

def extract_svg(text: str) -> str | None:
    """Extract SVG code from response."""
    # Remove markdown code blocks if present
    text = re.sub(r"```(xml|svg)?", "", text)
    text = text.replace("```", "")

    # Find svg tag
    start = text.find("<svg")
    end = text.find("</svg>")

    if start != -1 and end != -1:
        return text[start : end + 6]
    return None

def main():
    """Generate assets."""
    client = PipelineFactory.create_gemini_client()
    model_id = "gemini-flash-latest"

    output_dir = Path("docs/assets/images")
    output_dir.mkdir(parents=True, exist_ok=True)

    for i, asset in enumerate(ASSETS):
        if i > 0:
            logger.info("Sleeping for 60s to avoid rate limits...")
            time.sleep(60)

        logger.info(f"Generating {asset.filename} using {model_id} (SVG)...")

        try:
            response = client.models.generate_content(
                model=model_id,
                contents=asset.prompt,
            )

            if response.text:
                svg_content = extract_svg(response.text)
                if svg_content:
                    output_path = output_dir / asset.filename
                    output_path.write_text(svg_content, encoding="utf-8")
                    logger.info(f"Saved {asset.filename} to {output_path}")
                else:
                    logger.error(f"Could not extract SVG for {asset.filename}. Response: {response.text[:100]}...")
            else:
                logger.error(f"No text returned for {asset.filename}")

        except Exception as e:
            logger.error(f"Exception generating {asset.filename}: {e}", exc_info=True)

if __name__ == "__main__":
    main()
