from __future__ import annotations

from pathlib import Path
from typing import Literal

ModelType = Literal["writer", "enricher", "enricher_vision", "ranking", "editor", "embedding"]

class ModelConfig:
    embedding_output_dimensionality: int

    def __init__(self, cli_model: str | None = ..., site_config: dict | None = ...) -> None: ...
    def get_model(self, model_type: ModelType) -> str: ...


def load_site_config(output_dir: Path) -> dict: ...
