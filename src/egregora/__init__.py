"""Egregora v2: Multi-platform chat analysis and blog generation."""

# Dedupe API keys at import time to prevent SDK warning about both being set
# This must happen BEFORE any google.genai imports to be effective
from egregora.utils.env import dedupe_api_keys

dedupe_api_keys()

from egregora.orchestration.pipelines.write import process_whatsapp_export  # noqa: E402

__version__ = "2.0.0"
__all__ = [
    "process_whatsapp_export",
]
