# Simple Backlog Processing

This guide describes how to use the simplified backlog processor to transform WhatsApp conversation archives into daily newsletters.

## Overview

The simplified backlog processor is a lightweight script that:

1. Scans for ZIP files containing WhatsApp exports
2. Processes each file through the existing pipeline
3. Generates newsletters for each day
4. Provides clear progress feedback

## Prerequisites

- ZIP files from WhatsApp exports named with dates (e.g., `2024-10-01.zip`)
- `GEMINI_API_KEY` configured in environment
- Dependencies installed (`uv sync`)

## File Structure

```
project/
├── data/
│   └── whatsapp_zips/
│       ├── 2024-10-01.zip
│       └── 2024-10-02.zip
└── newsletters/
    ├── 2024-10-01.md
    └── 2024-10-02.md
```

## Usage

### Basic Processing

Process all ZIP files in a directory:

```bash
python scripts/process_backlog.py data/whatsapp_zips newsletters
```

### Skip Existing Files

By default, the script skips files that already have corresponding newsletters:

```bash
python scripts/process_backlog.py data/whatsapp_zips newsletters
# Output:
# 📊 Found 5 ZIP files
# ⏭️  2024-10-01 (already exists)
# ✅ 2024-10-02 -> docs/reports/daily/2024-10-02.md
# ✅ 2024-10-03 -> docs/reports/daily/2024-10-03.md
# 📈 Summary: 2 processed, 1 skipped, 0 failed
```

### Force Overwrite

To regenerate existing newsletters:

```bash
python scripts/process_backlog.py data/whatsapp_zips newsletters --force
```

## What was simplified?

The original complex system had:
- 1000+ lines across 6 modules
- Checkpoint/resume system
- Cost estimation
- Batch configuration
- Retry logic
- Complex logging
- Statistics tracking

The new simple approach:
- **70 lines** in a single script
- Uses the existing `Pipeline` class
- Simple iteration over ZIP files
- Basic error handling with clear output
- Skip existing files automatically

## Benefits

- **Much simpler**: Easy to understand and modify
- **Leverages existing code**: Uses the proven `Pipeline` class
- **Clear output**: Shows exactly what's happening
- **Robust**: Handles errors gracefully and continues processing
- **No dependencies**: No complex checkpoint or state management

## Troubleshooting

- **No ZIP files found**: Check that the ZIP directory path is correct
- **Processing errors**: The script will show the specific error and continue with the next file
- **Missing dates**: ZIP files must contain a date pattern (YYYY-MM-DD) in the filename

## Migration from Complex System

If you were using the old complex backlog system:

1. The new script automatically skips already processed files
2. Just run the simple script on your ZIP directory
3. Remove any old checkpoint files if desired

The simple approach does the same core job with 95% less code complexity.