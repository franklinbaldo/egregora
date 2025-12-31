#!/bin/bash
set -e

# Check if docs/adr directory exists
if [ ! -d "docs/adr" ]; then
  echo "Error: docs/adr directory is missing!"
  exit 1
fi

# Check if docs/adr is empty
if [ -z "$(ls -A docs/adr)" ]; then
  echo "Error: docs/adr directory is empty!"
  exit 1
fi

echo "Success: docs/adr exists and is not empty."
