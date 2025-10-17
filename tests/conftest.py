import sys
from pathlib import Path


def pytest_configure() -> None:
    root = Path(__file__).resolve().parents[1] / "src"
    if root.exists():
        sys.path.insert(0, str(root))
