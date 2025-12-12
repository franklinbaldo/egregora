"""Egregora orchestration layer.

Coordinates high-level workflows and pipelines:
- write_pipeline: Ingest → Process → Generate posts (write command)
- pipeline/context: Shared runtime context and state
- worker_base: Background task workers
"""

from egregora.orchestration.pipelines import write as write_pipeline

__all__ = ["write_pipeline"]
