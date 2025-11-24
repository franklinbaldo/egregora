"""Banner/cover image generation for blog posts.

Requires GOOGLE_API_KEY environment variable.
"""

from egregora.agents.banner.agent import (
    BannerInput,
    BannerOutput,
    generate_banner,
    is_banner_generation_available,
)

__all__ = [
    "BannerInput",
    "BannerOutput",
    "generate_banner",
    "is_banner_generation_available",
]
