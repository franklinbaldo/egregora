#!/usr/bin/env python3
"""Simple backlog processor - does the same job with 95% less code."""

from __future__ import annotations

import csv
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from egregora.config import PipelineConfig
from egregora.processor import UnifiedProcessor


@dataclass(slots=True)
class ProcessBacklogSummary:
    """Summary returned by :func:`process_backlog`."""

    zip_count: int
    groups_processed: int
    posts_generated: int
    undated_files: list[str]


def process_backlog(  # noqa: PLR0912
    zip_dir: str | Path,
    output_dir: str | Path,
    force: bool = False,
    *,
    verbose: bool = True,
    offline: bool = False,
) -> ProcessBacklogSummary:
    """Process all ZIP files using the unified processor."""

    zip_path = Path(zip_dir)
    out_path = Path(output_dir)

    if not zip_path.exists():
        if verbose:
            print(f"❌ ZIP directory not found: {zip_path}")
        return ProcessBacklogSummary(0, 0, 0, [])

    if force and out_path.exists():
        shutil.rmtree(out_path)

    out_path.mkdir(parents=True, exist_ok=True)

    config = PipelineConfig.with_defaults(
        zips_dir=zip_path,
        posts_dir=out_path,
    )

    if offline:
        config.enrichment.enabled = False
        config.cache.enabled = False
        config.rag.enabled = False
        config.profiles.enabled = False

    processor = UnifiedProcessor(config)

    zip_files = sorted(zip_path.glob("*.zip"))
    undated = [path.name for path in zip_files if not re.search(r"\d{4}-\d{2}-\d{2}", path.name)]
    if not zip_files:
        if verbose:
            print(f"📭 No ZIP files found in {zip_path}")
        return ProcessBacklogSummary(0, 0, 0, undated)

    if verbose:
        print(f"📊 Found {len(zip_files)} ZIP files")
        if undated:
            print("⚠️  Files without YYYY-MM-DD pattern will be ignored:")
            for name in undated:
                print(f"   • {name}")

    results = processor.process_all()

    total = sum(len(paths) for paths in results.values())
    summary = ProcessBacklogSummary(
        zip_count=len(zip_files),
        groups_processed=len(results),
        posts_generated=total,
        undated_files=undated,
    )

    if verbose:
        print("\n📈 Summary:")
        print(f"  Groups processed: {summary.groups_processed}")
        print(f"  Posts generated: {summary.posts_generated}")

        for slug, paths in sorted(results.items()):
            print(f"  • {slug}: {len(paths)} post(s)")

        metrics_path = processor.config.enrichment.metrics_csv_path
        if metrics_path:
            latest = _load_latest_metrics(Path(metrics_path))
            if latest:
                print("\n📈 Último enriquecimento registrado:")
                print(
                    "  - Início: {started_at} (duração {duration_seconds}s)".format(
                        started_at=latest.get("started_at", "?"),
                        duration_seconds=latest.get("duration_seconds", "?"),
                    )
                )
                print(
                    "  - Relevantes/Analisados: {relevant_items}/{analyzed_items} (limiar ≥{threshold})".format(
                        relevant_items=latest.get("relevant_items", "0"),
                        analyzed_items=latest.get("analyzed_items", "0"),
                        threshold=latest.get("threshold", "?"),
                    )
                )
                domains = latest.get("domains") or "-"
                print(f"  - Domínios: {domains}")
                errors = latest.get("errors") or "-"
                print(f"  - Erros: {errors}")

    return summary


def _load_latest_metrics(path: Path) -> dict[str, str] | None:
    if not path.exists() or not path.is_file():
        return None

    try:
        with path.open("r", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error):
        return None

    if not rows:
        return None
    return rows[-1]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Simple WhatsApp backlog processor")
    parser.add_argument("zip_dir", help="Directory containing ZIP files")
    parser.add_argument("output_dir", help="Output directory for posts")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Disable network-dependent features like enrichment and RAG",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output to a single summary line",
    )

    args = parser.parse_args()
    summary = process_backlog(
        args.zip_dir,
        args.output_dir,
        args.force,
        verbose=not args.quiet,
        offline=args.offline,
    )

    if args.quiet:
        print(
            f"Processed {summary.zip_count} ZIP(s), {summary.groups_processed} group(s), "
            f"{summary.posts_generated} post(s)"
        )
