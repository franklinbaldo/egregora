"""Banner/cover image generation for blog posts.

Requires GOOGLE_API_KEY environment variable.
"""

from egregora.agents.banner.generator import (
    BannerGenerator,
    BannerRequest,
    BannerResult,
    generate_banner_for_post,
    is_banner_generation_available,
)

__all__ = [
    "BannerGenerator",
    "BannerRequest",
    "BannerResult",
    "generate_banner_for_post",
    "is_banner_generation_available",
]
