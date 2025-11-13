"""High-level orchestration layer for Egregora workflows.

This package coordinates business-level workflows that combine multiple pipeline
stages to accomplish specific user goals. Each module represents a distinct
user-facing command or workflow.

Architecture:
- orchestration/ (THIS) → Business workflows (WHAT to execute)
- pipeline/ → Generic infrastructure (HOW to execute)
- data_primitives/ → Core data models

Current workflows:
- write_pipeline: Ingest → Process → Generate posts (write command)

Future workflows:
- read_pipeline: Read published content for commenting/rating (read command)
- edit_pipeline: Apply feedback and edit published content (edit command)
"""

from egregora.orchestration import write_pipeline

__all__ = ["write_pipeline"]
