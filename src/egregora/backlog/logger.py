"""Logging helpers tailored for backlog processing."""

from __future__ import annotations

import logging
from pathlib import Path

from ..config import BacklogConfig


def configure_logger(
    config: BacklogConfig,
    *,
    name: str = "egregora.backlog",
    stream: bool = False,
) -> logging.Logger:
    """Configure and return a shared logger for backlog tooling."""

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = getattr(logging, config.logging.level.upper(), logging.INFO)
    logger.setLevel(level)

    log_file = Path(config.logging.file).expanduser()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if stream:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    logger.propagate = False
    return logger


__all__ = ["configure_logger"]
