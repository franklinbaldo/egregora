#!/usr/bin/env python3
"""CLI tool to monitor memory during blog generation.

Usage:
    ./scripts/monitor_memory.py /path/to/output-dir

This will monitor memory every 5 seconds and save to:
    /path/to/output-dir/.egregora/memory_profile.csv
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from egregora.utils.memory import (
    MemoryMonitor,
    diagnose_memory_issues,
)


def main() -> None:
    """Monitor memory usage."""
    if len(sys.argv) < 2:
        sys.exit(1)

    output_dir = Path(sys.argv[1])

    # Parse options
    diagnose = "--diagnose" in sys.argv
    interval = 5.0
    if "--interval" in sys.argv:
        idx = sys.argv.index("--interval")
        if idx + 1 < len(sys.argv):
            interval = float(sys.argv[idx + 1])

    if diagnose:
        # Run diagnostics
        zip_path = None
        for parent in [Path.cwd(), output_dir.parent]:
            for pattern in ["*.zip", "real-whatsapp-export.zip"]:
                matches = list(parent.glob(pattern))
                if matches:
                    zip_path = matches[0]
                    break
            if zip_path:
                break

        lancedb_dir = output_dir / ".egregora" / "lancedb"

        diagnose_memory_issues(zip_path=zip_path, lancedb_dir=lancedb_dir)
        return

    # Start continuous monitoring

    monitor = MemoryMonitor(interval=interval, log_file=output_dir / ".egregora" / "memory_profile.csv")

    try:
        monitor.start()

        # Keep running until interrupted
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        monitor.stop()


if __name__ == "__main__":
    main()
