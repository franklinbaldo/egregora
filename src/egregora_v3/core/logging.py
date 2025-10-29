import logging
import sys
from pathlib import Path

from egregora_v3.core.paths import LOGS_DIR


def setup_logging(log_level: str = "INFO", log_file: Path = LOGS_DIR / "egregora.log"):
    """
    Configures logging for the application.
    """
    log_level = log_level.upper()

    # Ensure the logs directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Basic configuration
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Quieten down noisy libraries
    logging.getLogger("pydantic").setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger instance for a given module.
    """
    return logging.getLogger(name)
