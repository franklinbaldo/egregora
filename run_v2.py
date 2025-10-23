#!/usr/bin/env python3
"""
Standalone runner for Egregora v2 (ultra-simple pipeline)

Usage:
  python run_v2.py process --zip_file=export.zip --output=./blog --gemini_key=KEY
"""

from src.egregora.cli import main

if __name__ == "__main__":
    main()
