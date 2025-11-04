"""Banner/cover image generation for blog posts using Gemini image generation."""

import logging
import mimetypes
import os
from pathlib import Path

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class BannerGenerator:
    """Generate cover images for blog posts using Gemini 2.5 Flash Image."""

    def __init__(self, api_key: str | None = None):
        """Initialize the banner generator.

        Args:
            api_key: Gemini API key. If None, reads from GEMINI_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be provided or set in environment")

        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.5-flash-image"

    def generate_banner(
        self,
        post_title: str,
        post_summary: str,
        output_dir: Path,
        slug: str,
    ) -> Path | None:
        """Generate a banner image for a blog post.

        Args:
            post_title: The blog post title
            post_summary: Brief summary of the post
            output_dir: Directory to save the generated banner
            slug: Post slug (used for filename)

        Returns:
            Path to the generated banner image, or None if generation failed
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Construct the prompt for image generation
        prompt = self._build_prompt(post_title, post_summary)

        try:
            logger.info(f"Generating banner for post: {post_title}")

            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                )
            ]

            generate_content_config = types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                image_config=types.ImageConfig(
                    aspect_ratio="1:1",  # Square format for blog banners
                ),
                system_instruction=[
                    types.Part.from_text(
                        text=(
                            "You are a senior editorial illustrator for a modern blog. "
                            "Your job is to translate an article into a striking, concept-driven "
                            "cover/banner image that is legible at small sizes, brand-consistent, "
                            "and accessible. Create minimalist, abstract representations that "
                            "capture the essence of the article without literal depictions. "
                            "Use bold colors, clear composition, and modern design principles."
                        )
                    )
                ],
            )

            # Generate the image
            for chunk in self.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=generate_content_config,
            ):
                if not (
                    chunk.candidates
                    and chunk.candidates[0].content
                    and chunk.candidates[0].content.parts
                ):
                    continue

                part = chunk.candidates[0].content.parts[0]

                # Check for image data
                if part.inline_data and part.inline_data.data:
                    inline_data = part.inline_data
                    data_buffer = inline_data.data
                    file_extension = mimetypes.guess_extension(inline_data.mime_type)

                    # Save the banner
                    banner_filename = f"banner-{slug}{file_extension}"
                    banner_path = output_dir / banner_filename

                    with open(banner_path, "wb") as f:
                        f.write(data_buffer)

                    logger.info(f"Banner saved to: {banner_path}")
                    return banner_path

                # Log any text responses
                if hasattr(chunk, "text") and chunk.text:
                    logger.debug(f"Gemini response: {chunk.text}")

            logger.warning(f"No image generated for post: {post_title}")
            return None

        except Exception as e:
            logger.error(f"Failed to generate banner for {post_title}: {e}")
            return None

    def _build_prompt(self, title: str, summary: str) -> str:
        """Build the prompt for banner image generation.

        Args:
            title: Post title
            summary: Post summary

        Returns:
            Prompt string for image generation
        """
        return f"""Create a cover image for this blog post:

Title: {title}

Summary: {summary}

Requirements:
- Modern, minimalist design
- Abstract/conceptual (not literal)
- Bold, striking visual
- Suitable for blog banner/header
- Legible when scaled down
- Professional and engaging

The image should capture the essence and mood of the article while being visually
distinct and memorable."""


def generate_banner_for_post(
    post_title: str,
    post_summary: str,
    output_dir: Path,
    slug: str,
    api_key: str | None = None,
) -> Path | None:
    """Convenience function to generate a banner for a post.

    Args:
        post_title: The blog post title
        post_summary: Brief summary of the post
        output_dir: Directory to save the banner
        slug: Post slug (for filename)
        api_key: Optional Gemini API key

    Returns:
        Path to generated banner, or None if failed
    """
    try:
        generator = BannerGenerator(api_key=api_key)
        return generator.generate_banner(post_title, post_summary, output_dir, slug)
    except Exception as e:
        logger.error(f"Banner generation failed: {e}")
        return None
