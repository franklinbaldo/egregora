"""Abstractions for banner image generation providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class ImageGenerationRequest:
    """Request parameters for generating an image."""

    prompt: str
    response_modalities: Sequence[str]
    aspect_ratio: str | None = None


@dataclass
class ImageGenerationResult:
    """Normalized response from an image generation provider."""

    image_bytes: bytes
    mime_type: str
    debug_text: str | None = None

    @property
    def has_image(self) -> bool:
        """True when binary image data is available."""
        return bool(self.image_bytes) and bool(self.mime_type)


class ImageGenerationProvider(Protocol):
    """Protocol for providers capable of generating images."""

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate an image using provider-specific implementation."""
