#!/usr/bin/env python3
"""Simple backlog processor - does the same job with 95% less code."""

from __future__ import annotations

import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from egregora.config import PipelineConfig
from egregora.processor import UnifiedProcessor


@dataclass(slots=True)
class BacklogSummary:
    """Structured result produced by :func:`process_backlog`."""

    zip_dir: Path
    output_dir: Path
    zip_count: int
    groups_processed: int
    posts_generated: int
    per_group: dict[str, int]
    undated_files: list[str]


def process_backlog(
    zip_dir: str | Path,
    output_dir: str | Path,
    *,
    force: bool = False,
    verbose: bool = True,
) -> BacklogSummary:
    """Process all ZIP files using the unified processor and return a summary."""

    zip_path = Path(zip_dir)
    out_path = Path(output_dir)

    if not zip_path.exists():
        raise FileNotFoundError(f"ZIP directory not found: {zip_path}")

    if force and out_path.exists():
        shutil.rmtree(out_path)

    out_path.mkdir(parents=True, exist_ok=True)

    zip_files = sorted(zip_path.glob("*.zip"))
    undated = sorted(
        path.name for path in zip_files if not re.search(r"\d{4}-\d{2}-\d{2}", path.name)
    )

    if not zip_files:
        if verbose:
            print(f"📭 No ZIP files found in {zip_path}")
        return BacklogSummary(
            zip_dir=zip_path,
            output_dir=out_path,
            zip_count=0,
            groups_processed=0,
            posts_generated=0,
            per_group={},
            undated_files=[],
        )

    if verbose:
        print(f"📊 Found {len(zip_files)} ZIP files")
        if undated:
            print("⚠️  Files without YYYY-MM-DD pattern will be ignored:")
            for name in undated:
                print(f"   • {name}")

    config = PipelineConfig.with_defaults(
        zips_dir=zip_path,
        posts_dir=out_path,
    )

    processor = UnifiedProcessor(config)
    results = processor.process_all()
    per_group = {slug: len(paths) for slug, paths in sorted(results.items())}

    summary = BacklogSummary(
        zip_dir=zip_path,
        output_dir=out_path,
        zip_count=len(zip_files),
        groups_processed=len(per_group),
        posts_generated=sum(per_group.values()),
        per_group=per_group,
        undated_files=undated,
    )

    if verbose:
        print("\n📈 Summary:")
        print(f"  Groups processed: {summary.groups_processed}")
        print(f"  Posts generated: {summary.posts_generated}")
        for slug, count in summary.per_group.items():
            print(f"  • {slug}: {count} post(s)")

    return summary


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Simple WhatsApp backlog processor")
    parser.add_argument("zip_dir", help="Directory containing ZIP files")
    parser.add_argument("output_dir", help="Output directory for posts")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")

    args = parser.parse_args()

    try:
        process_backlog(args.zip_dir, args.output_dir, force=args.force)
    except FileNotFoundError as error:
        print(f"❌ {error}")
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
