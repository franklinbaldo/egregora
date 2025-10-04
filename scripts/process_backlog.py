#!/usr/bin/env python3
"""Simple backlog processor - does the same job with 95% less code."""

import re
import sys
from pathlib import Path
from datetime import datetime

from egregora.pipeline import Pipeline
from egregora.config import PipelineConfig


def process_backlog(zip_dir: str, output_dir: str, force: bool = False):
    """Process all ZIP files through the existing pipeline."""
    zip_path = Path(zip_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    if not zip_path.exists():
        print(f"❌ ZIP directory not found: {zip_path}")
        return
    
    config = PipelineConfig.with_defaults(
        zips_dir=zip_path,
        newsletters_dir=out_path,
        media_dir=out_path / "media"
    )
    pipeline = Pipeline(config)
    
    processed = 0
    skipped = 0
    failed = 0
    
    # Find and process all dated ZIP files
    zip_files = sorted(zip_path.glob("*.zip"))
    if not zip_files:
        print(f"📭 No ZIP files found in {zip_path}")
        return
        
    print(f"📊 Found {len(zip_files)} ZIP files")
    
    for zip_file in zip_files:
        # Extract date from filename (YYYY-MM-DD pattern)
        match = re.search(r"(\d{4}-\d{2}-\d{2})", zip_file.name)
        if not match:
            print(f"⚠️  Skipping {zip_file.name} (no date pattern)")
            continue
            
        date_str = match.group(1)
        try:
            archive_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            print(f"⚠️  Skipping {zip_file.name} (invalid date: {date_str})")
            continue
            
        output_file = out_path / f"{date_str}.md"
        
        # Skip if already exists (unless force)
        if output_file.exists() and not force:
            print(f"⏭️  {date_str} (already exists)")
            skipped += 1
            continue
            
        try:
            result = pipeline.process_day(zip_file, archive_date)
            if result and result.output_path:
                print(f"✅ {date_str} -> {result.output_path}")
                processed += 1
            else:
                print(f"❌ {date_str}: No output generated")
                failed += 1
        except Exception as e:
            print(f"❌ {date_str}: {e}")
            failed += 1
    
    print(f"\n📈 Summary: {processed} processed, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple WhatsApp backlog processor")
    parser.add_argument("zip_dir", help="Directory containing ZIP files")
    parser.add_argument("output_dir", help="Output directory for newsletters")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    
    args = parser.parse_args()
    process_backlog(args.zip_dir, args.output_dir, args.force)