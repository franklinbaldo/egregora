"""Project-wide pytest fixtures available to the suite."""

from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_framework.conftest import *  # noqa: F401,F403
