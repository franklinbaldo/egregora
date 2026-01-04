#!/bin/bash
set -ex

echo "============================================="
echo ">>> Running Consolidated Quality Checks <<<"
echo "============================================="

echo "--- Running Vulture ---"
uv run vulture src tests vulture_whitelist.py --min-confidence=80

echo "--- Running Radon CC ---"
uvx radon cc src -n C --total-average

echo "--- Running Radon MI ---"
uvx radon mi src -n B

echo "--- Running Xenon ---"
uvx xenon src --max-absolute E --max-modules C --max-average B --exclude "*/database/*.py"

echo "--- Running Bandit ---"
uvx bandit -r src -f screen -c pyproject.toml -lll -ii

echo "--- Running Private Imports Check ---"
python dev_tools/check_private_imports.py

echo "--- Running Test Config Check ---"
python dev_tools/check_test_config.py

echo "--- Running Unit Tests ---"
uv run pytest tests/unit/ -x -q --tb=line

echo "--- Running Coverage Check ---"
uv run pytest tests/unit/ --cov=src/egregora --cov-report=term-missing -q

echo "============================================="
echo ">>> Quality Checks Complete <<<"
echo "============================================="
