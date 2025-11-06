"""Configuration loader for .egregora/config.yml (ALPHA VERSION - NO BACKWARD COMPAT).

This module provides simple configuration loading for Egregora in alpha.

Strategy: Clean break, no backward compatibility
- ONLY loads from .egregora/config.yml
- Creates default config if missing
- No mkdocs.yml fallback
- No legacy transformation
- No deprecation warnings

We're in alpha - we can break everything to make it better!
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from egregora.config.schema import EgregoraConfig

logger = logging.getLogger(__name__)


def find_egregora_config(start_dir: Path) -> Path | None:
    """Search upward for .egregora/config.yml.

    Args:
        start_dir: Starting directory for upward search

    Returns:
        Path to .egregora/config.yml if found, else None
    """
    current = start_dir.expanduser().resolve()
    for candidate in (current, *current.parents):
        config_path = candidate / ".egregora" / "config.yml"
        if config_path.exists():
            return config_path
    return None


def load_egregora_config(site_root: Path) -> EgregoraConfig:
    """Load Egregora configuration from .egregora/config.yml.

    SIMPLE: Just load .egregora/config.yml, create if missing. That's it!

    Args:
        site_root: Root directory of the site

    Returns:
        Validated EgregoraConfig instance

    Raises:
        ValidationError: If config file contains invalid data
    """
    config_path = site_root / ".egregora" / "config.yml"

    if not config_path.exists():
        logger.info("No .egregora/config.yml found, creating default config")
        return create_default_config(site_root)

    logger.info("Loading config from %s", config_path)

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return EgregoraConfig(**data)
    except yaml.YAMLError as e:
        logger.error("Failed to parse %s: %s", config_path, e)
        logger.warning("Creating default config due to YAML error")
        return create_default_config(site_root)
    except Exception as e:
        logger.error("Invalid config in %s: %s", config_path, e)
        logger.warning("Creating default config due to validation error")
        return create_default_config(site_root)


def create_default_config(site_root: Path) -> EgregoraConfig:
    """Create default .egregora/config.yml and return it.

    Args:
        site_root: Root directory of the site

    Returns:
        EgregoraConfig with all defaults
    """
    config = EgregoraConfig()  # All defaults from Pydantic
    save_egregora_config(config, site_root)
    logger.info("Created default config at %s/.egregora/config.yml", site_root)
    return config


def save_egregora_config(config: EgregoraConfig, site_root: Path) -> Path:
    """Save EgregoraConfig to .egregora/config.yml.

    Creates .egregora/ directory if it doesn't exist.

    Args:
        config: EgregoraConfig instance to save
        site_root: Root directory of the site

    Returns:
        Path to the saved config file
    """
    egregora_dir = site_root / ".egregora"
    egregora_dir.mkdir(exist_ok=True, parents=True)

    config_path = egregora_dir / "config.yml"

    # Export as dict
    data = config.model_dump(exclude_defaults=False, mode="python")

    # Write with nice formatting
    yaml_str = yaml.dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )

    config_path.write_text(yaml_str, encoding="utf-8")
    logger.debug("Saved config to %s", config_path)

    return config_path


__all__ = [
    "find_egregora_config",
    "load_egregora_config",
    "create_default_config",
    "save_egregora_config",
]
