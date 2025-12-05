from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ModelSettings:
    name: str | None = None


@dataclass
class RAGSettings:
    enabled: bool = False


def create_default_config(config_path: str | Path | None = None) -> dict[str, Any]:
    return {}
