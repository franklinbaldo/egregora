"""Registry initialization for input sources and output formats.

This module automatically registers all available input sources and output formats
when imported. Add new implementations to this module to make them available.

Note: Template implementations (Slack, Hugo) are NOT registered by default.
They are examples showing how to implement new sources/formats and need
completion before being production-ready.
"""

from egregora.ingestion.base import input_registry
from egregora.ingestion.whatsapp_input import WhatsAppInputSource
from egregora.rendering.base import output_registry
from egregora.rendering.mkdocs import MkDocsOutputFormat


def register_all() -> None:
    """Register all production-ready input sources and output formats.

    Note: Template implementations are not registered:
    - SlackInputSource: Template in ingestion/slack_input.py (needs completion)
    - HugoOutputFormat: Template in init/hugo_output.py (needs completion)

    To enable templates, complete their implementation and add them here.
    """
    # Register production input sources
    input_registry.register(WhatsAppInputSource)

    # Register production output formats
    output_registry.register(MkDocsOutputFormat)

    # Templates (commented out - complete implementation first):
    # from egregora.ingestion.slack_input import SlackInputSource
    # input_registry.register(SlackInputSource)
    # from egregora.rendering.hugo import HugoOutputFormat
    # output_registry.register(HugoOutputFormat)


# Auto-register on import
register_all()


__all__ = [
    "input_registry",
    "output_registry",
    "register_all",
]
