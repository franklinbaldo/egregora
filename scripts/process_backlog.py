#!/usr/bin/env python3
"""Simple backlog processor - does the same job with 95% less code."""

import csv
import re
import shutil
import sys
from pathlib import Path

from egregora.config import PipelineConfig
from egregora.processor import UnifiedProcessor


def process_backlog(zip_dir: str, output_dir: str, force: bool = False):
    """Process all ZIP files using the unified processor."""

    zip_path = Path(zip_dir)
    out_path = Path(output_dir)

    if not zip_path.exists():
        print(f"❌ ZIP directory not found: {zip_path}")
        return

    if force and out_path.exists():
        shutil.rmtree(out_path)

    out_path.mkdir(parents=True, exist_ok=True)

    config = PipelineConfig.with_defaults(
        zips_dir=zip_path,
        posts_dir=out_path,
    )

    processor = UnifiedProcessor(config)

    zip_files = sorted(zip_path.glob("*.zip"))
    if not zip_files:
        print(f"📭 No ZIP files found in {zip_path}")
        return

    print(f"📊 Found {len(zip_files)} ZIP files")
    undated = [path.name for path in zip_files if not re.search(r"\d{4}-\d{2}-\d{2}", path.name)]
    if undated:
        print("⚠️  Files without YYYY-MM-DD pattern will be ignored:")
        for name in undated:
            print(f"   • {name}")

    results = processor.process_all()

    total = sum(len(paths) for paths in results.values())
    print("\n📈 Summary:")
    print(f"  Groups processed: {len(results)}")
    print(f"  Posts generated: {total}")

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

    args = parser.parse_args()
    process_backlog(args.zip_dir, args.output_dir, args.force)