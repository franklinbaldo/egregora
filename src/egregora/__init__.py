"""Egregora v2: Agent-based WhatsApp to blog pipeline."""

from .core.models import Message, Topic, Post, Profile
from .pipeline import Pipeline

__version__ = "2.0.0"

__all__ = [
    "Message",
    "Topic",
    "Post",
    "Profile",
    "Pipeline",
]
