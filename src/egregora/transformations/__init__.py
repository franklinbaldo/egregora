"""Pure functional transformations for Table → Table data manipulation.

This package contains reusable, functional components that transform Ibis tables
without side effects. These are the core data manipulation utilities used by the
orchestration layer to build data processing workflows.

**Philosophy**: Functional, composable transformations with no state or side effects.

What's Exported:
----------------

**Windowing** (windowing.py):
  - `create_windows`: Split tables into sequential windows by messages/time/bytes
  - `Window`: Window data structure with metadata
  - `load_checkpoint`, `save_checkpoint`: Resume logic via sentinel files
  - `split_window_into_n_parts`: Parallel processing utilities

**Media Processing** (media.py):
  - `process_media_for_window`: Extract and standardize media references
  - `extract_markdown_media_refs`: Find media references in messages
  - `replace_markdown_media_refs`: Update references with UUID-based filenames

Architecture Context:
---------------------

transformations/ sits in the middle layer of Egregora's architecture:

  orchestration/     → High-level workflows (WHAT to execute)
  transformations/   → Pure functional utilities (HOW to transform data)
  database/          → Persistence + infrastructure (WHERE to store/track)

All transformations operate on Ibis Table objects and preserve the IR schema
contract defined in :mod:`egregora.database.ir_schema`.

Examples
--------
Windowing by message count:
    >>> from egregora.transformations import create_windows
    >>> windows = create_windows(table, step_size=100, step_unit="messages")

Media processing:
    >>> from egregora.transformations import process_media_for_window
    >>> updated_table, mapping = process_media_for_window(
    ...     table,
    ...     adapter,
    ...     url_convention,
    ...     url_context,
    ... )

"""

from egregora.ops.media import (
    extract_media_references,
    process_media_for_window,
    replace_media_references,
)
from egregora.transformations.windowing import (
    Window,
    WindowConfig,
    create_windows,
    load_checkpoint,
    save_checkpoint,
    split_window_into_n_parts,
)

__all__ = [
    "WindowConfig",
    "create_windows",
    "extract_media_references",
    "generate_window_signature",
    "load_checkpoint",
    "process_media_for_window",
    "replace_media_references",
    "save_checkpoint",
    "split_window_into_n_parts",
]
