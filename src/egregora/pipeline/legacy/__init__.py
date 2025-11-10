"""Legacy pipeline code (deprecated).

This module contains deprecated code that is kept for backward compatibility
but should not be used in new code. It will be removed in a future version.

DEPRECATED:
- checkpoint.py: Old content-addressed checkpointing (replaced by tracking.py)

Use the modern alternatives instead:
- For resume logic: Use sentinel files (pipeline.windowing.load_checkpoint)
- For tracking: Use pipeline.tracking module
"""

from egregora.pipeline.legacy.checkpoint import (
    checkpoint_path,
    get_config_hash,
    run_with_checkpointing,
)
from egregora.pipeline.legacy.checkpoint import (
    load_checkpoint as load_content_checkpoint,
)
from egregora.pipeline.legacy.checkpoint import (
    save_checkpoint as save_content_checkpoint,
)

__all__ = [
    "checkpoint_path",
    "get_config_hash",
    "load_content_checkpoint",
    "run_with_checkpointing",
    "save_content_checkpoint",
]
