"""Vulture whitelist for known false positives.

This file tells vulture about intentional "unused" code that shouldn't be flagged.
Only includes v3 code and test mocks - v2 code should be kept clean with actual fixes.
"""

# V3: __exit__ method signature (required by context manager protocol)
# src/egregora_v3/infra/adapters/rss.py
_.exc_type
_.exc_val
_.exc_tb

# Tests: Mock method parameters used as keyword arguments
# tests/unit/agents/banner/test_gemini_provider.py
_.file
