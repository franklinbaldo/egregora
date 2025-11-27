"""Abstractions for banner image generation providers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ImageGenerationRequest:
    """Request parameters for generating an image."""

    prompt: str
    response_modalities: Sequence[str]
    aspect_ratio: str | None = None


@dataclass
class ImageGenerationResult:
    """Normalized response from an image generation provider."""

    image_bytes: bytes | None
    mime_type: str | None
    debug_text: str | None = None
    error: str | None = None
    error_code: str | None = None

    @property
    def has_image(self) -> bool:
        """True when binary image data is available."""
        return self.image_bytes is not None and self.mime_type is not None


class ImageGenerationProvider(Protocol):
    """Protocol for providers capable of generating images."""

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate an image using provider-specific implementation."""
