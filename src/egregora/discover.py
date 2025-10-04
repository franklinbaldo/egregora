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

    def get(self, format: str = "human") -> str:
        """Return the anonymized identifier in its canonical representation."""

        if format != "human":
            return ""
        return self.variants.get("human", "")


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


def format_cli_message(result: DiscoveryResult) -> str:
    """Return a human readable message summarising ``result``."""

    lines = [
        "📛 Autodescoberta de identificador anônimo",
        f"• Entrada original: {result.raw_input}",
        f"• Tipo detectado: {result.detected_type}",
        f"• Forma normalizada: {result.normalized}",
        f"• Identificador anônimo: {result.get()}",
    ]
    return "\n".join(lines)


__all__ = [
    "DiscoveryResult",
    "discover_identifier",
    "format_cli_message",
    "detect_type",
]
