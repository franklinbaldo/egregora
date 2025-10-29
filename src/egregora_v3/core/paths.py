import os
from pathlib import Path


def get_app_dir(app_name: str = "egregora_v3") -> Path:
    """
    Returns the XDG-aware application directory for data, logs, and cache.
    """
    if "XDG_DATA_HOME" in os.environ:
        return Path(os.environ["XDG_DATA_HOME"]) / app_name
    else:
        return Path.home() / ".local" / "share" / app_name

def get_rag_dir(app_dir: Path) -> Path:
    """Returns the directory for RAG data."""
    return app_dir / "rag"

def get_logs_dir(app_dir: Path) -> Path:
    """Returns the directory for logs."""
    return app_dir / "logs"

def get_cache_dir(app_dir: Path) -> Path:
    """Returns the directory for cache."""
    return app_dir / "cache"

def ensure_dirs_exist():
    """Ensures all necessary application directories exist."""
    app_dir = get_app_dir()
    get_rag_dir(app_dir).mkdir(parents=True, exist_ok=True)
    get_logs_dir(app_dir).mkdir(parents=True, exist_ok=True)
    get_cache_dir(app_dir).mkdir(parents=True, exist_ok=True)

APP_DIR = get_app_dir()
RAG_DIR = get_rag_dir(APP_DIR)
LOGS_DIR = get_logs_dir(APP_DIR)
CACHE_DIR = get_cache_dir(APP_DIR)
