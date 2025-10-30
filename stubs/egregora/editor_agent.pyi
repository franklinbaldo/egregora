from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.genai import Client

from .model_config import ModelConfig

@dataclass
class EditorResult:
    final_content: str
    decision: str
    notes: str
    edits_made: bool
    tool_calls: list[dict[str, Any]]


def run_editor_session(
    post_path: Path,
    client: Client,
    model_config: ModelConfig,
    rag_dir: Path,
) -> EditorResult: ...
