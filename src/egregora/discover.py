"""Utilities for discovering anonymized identifiers from local inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .anonymizer import Anonymizer

DiscoveryType = Literal["phone", "nickname"]


@dataclass(slots=True)
class DiscoveryResult:
    """Information about the anonymized identifier for a given input."""

    raw_input: str
    normalized: str
    detected_type: DiscoveryType
    variants: dict[str, str]

    def get(self, format_name: str = "human") -> str:
        """Return the anonymized identifier in the requested format."""

        return self.variants.get(format_name, "")


def detect_type(value: str) -> DiscoveryType:
    """Heuristically determine whether ``value`` is a phone or nickname."""

    cleaned = value.strip().replace(" ", "").replace("-", "")
    if cleaned.startswith("+") or cleaned.isdigit():
        return "phone"
    return "nickname"


def discover_identifier(value: str) -> DiscoveryResult:
    """Return anonymization metadata for ``value``."""

    value = value.strip()
    if not value:
        raise ValueError("O valor informado está vazio.")

    detected = detect_type(value)
    if detected == "phone":
        normalized = Anonymizer.normalize_phone(value)
    else:
        normalized = Anonymizer.normalize_nickname(value)

    variants = Anonymizer.get_uuid_variants(value)
    return DiscoveryResult(
        raw_input=value,
        normalized=normalized,
        detected_type=detected,
        variants=variants,
    )


__all__ = [
    "DiscoveryResult",
    "discover_identifier",
    "detect_type",
]
