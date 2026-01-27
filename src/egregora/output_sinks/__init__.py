"""Output rendering for different site generators."""

from pathlib import Path
from typing import Any

from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.document import UrlContext
from egregora.output_sinks.base import (
    BaseOutputSink,
    OutputSinkRegistry,
    create_output_registry,
    create_output_sink,
)
from egregora.output_sinks.mkdocs import MkDocsAdapter, MkDocsPaths


def create_default_output_registry() -> OutputSinkRegistry:
    """Create a registry pre-populated with built-in adapters."""
    registry = create_output_registry()
    registry.register(MkDocsAdapter)
    return registry


def create_and_initialize_adapter(
    config: EgregoraConfig,
    output_dir: Path,
    *,
    site_root: Path | None = None,
    registry: OutputSinkRegistry | None = None,
    url_context: UrlContext | None = None,
    storage: Any | None = None,
) -> Any:
    """Create and initialize the output adapter for the pipeline.

    Args:
        config: Egregora configuration
        output_dir: Output directory
        site_root: Site root directory (optional)
        registry: Output sink registry (optional)
        url_context: URL context for canonical URLs (optional)
        storage: DuckDBStorageManager for database-backed reading (optional)

    Returns:
        Initialized output adapter

    """
    resolved_output = output_dir.expanduser().resolve()
    site_paths = MkDocsPaths(resolved_output, config=config)

    root = site_root or site_paths.site_root

    registry = registry or create_default_output_registry()

    adapter = registry.detect_format(root)
    if adapter is None:
        adapter = create_output_sink(root, format_type="mkdocs", registry=registry)

    adapter.initialize(root, url_context=url_context, storage=storage)
    return adapter


__all__ = [
    "BaseOutputSink",
    "MkDocsAdapter",
    "OutputSinkRegistry",
    "create_and_initialize_adapter",
    "create_default_output_registry",
    "create_output_registry",
    "create_output_sink",
]
