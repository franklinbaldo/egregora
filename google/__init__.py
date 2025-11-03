# Minimal google namespace package for tests.
from pathlib import Path
from types import SimpleNamespace

__path__: list[str] = [str(Path(__file__).resolve().parent)]

genai = SimpleNamespace()
