#!/usr/bin/env bash
# Run the Jules scheduler
# Usage: run-scheduler.sh [--all] [--dry-run] [--reset] [--prompt-id <id>]
#
# Environment variables required:
#   JULES_API_KEY - Jules API key
#   GITHUB_TOKEN - GitHub token
#   PYTHONPATH - Should include .team

set -euo pipefail

args=(tick)

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --all)
      args+=(--all)
      shift
      ;;
    --dry-run)
      args+=(--dry-run)
      shift
      ;;
    --reset)
      args+=(--reset)
      shift
      ;;
    --prompt-id)
      args+=(--prompt-id "$2")
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

echo "🚀 Running Jules Scheduler with args: ${args[*]}"
uv run python -m repo.cli schedule "${args[@]}"
