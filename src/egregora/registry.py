"""Registry initialization for input sources and output formats.

This module automatically registers all available input sources and output formats
when imported. Add new implementations to this module to make them available.

Note: Template implementations (Slack, Hugo) are NOT registered by default.
They are examples showing how to implement new sources/formats and need
completion before being production-ready.
"""

from egregora.rendering.base import output_registry

# Registry uses old mkdocs.py (two-phase init: __init__() + initialize())
# Writer agent uses new mkdocs_output_format.py directly
from egregora.rendering.mkdocs import MkDocsOutputFormat
from egregora.sources.base import input_registry
from egregora.sources.whatsapp.input import WhatsAppInputSource


def register_all() -> None:
    """Register all production-ready input sources and output formats.

    Note: Template implementations are not registered:
    - SlackInputSource: Template in ingestion/slack_input.py (needs completion)
    - HugoOutputFormat: Template in rendering/hugo.py (needs completion)

    To enable templates, complete their implementation and add them here.
    """
    input_registry.register(WhatsAppInputSource)
    output_registry.register(MkDocsOutputFormat)


register_all()
__all__ = ["input_registry", "output_registry"]
