"""V3-specific test configuration.

This conftest prevents V2 dependencies from loading.
"""

import sys
from pathlib import Path

# Add src to path for V3 imports
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))
