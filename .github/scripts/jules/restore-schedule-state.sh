#!/usr/bin/env bash
# Restore schedule state from artifact or fall back to repo seed
# Usage: restore-schedule-state.sh
#
# Expects artifact files (if downloaded) to be in current directory:
#   schedule.csv
#   oracle_schedule.csv

set -euo pipefail

if [ -f "schedule.csv" ]; then
  echo "✅ Found schedule state from previous run"
  cp schedule.csv .team/schedule.csv

  if [ -f "oracle_schedule.csv" ]; then
    cp oracle_schedule.csv .team/oracle_schedule.csv
  fi
else
  echo "ℹ️ No previous artifact found, using repo file as seed"
fi
