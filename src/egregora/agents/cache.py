"""Domain-specific caching for agent operations."""
from __future__ import annotations
import logging
from hashlib import sha256
from typing import Annotated
logger = logging.getLogger(__name__)
ENRICHMENT_CACHE_VERSION = "v2"
