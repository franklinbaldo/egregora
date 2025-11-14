#!/bin/bash
# VCR Recording Script for Egregora
#
# Purpose: Record LLM API interactions for offline testing
# Usage: GOOGLE_API_KEY="your-key" ./scripts/record_vcr_cassettes.sh
#
# This script runs the egregora pipeline with VCR recording enabled,
# capturing all LLM API interactions to cassette files in tests/cassettes/

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Egregora VCR Recording Script ===${NC}\n"

# Check for API key
if [ -z "${GOOGLE_API_KEY:-}" ]; then
    echo -e "${RED}ERROR: GOOGLE_API_KEY environment variable not set${NC}"
    echo "Usage: GOOGLE_API_KEY=\"your-key\" $0"
    exit 1
fi

echo -e "${GREEN}✓ API key found${NC}"

# Check for test fixture
TEST_ZIP="tests/fixtures/whatsapp/minimal_export.zip"
if [ ! -f "$TEST_ZIP" ]; then
    echo -e "${RED}ERROR: Test fixture not found: $TEST_ZIP${NC}"
    echo "Available fixtures:"
    find tests/fixtures -name "*.zip" 2>/dev/null || echo "  (none found)"
    exit 1
fi

echo -e "${GREEN}✓ Test fixture found: $TEST_ZIP${NC}"

# Create output directory
OUTPUT_DIR="./test_output_vcr"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

echo -e "${GREEN}✓ Output directory created: $OUTPUT_DIR${NC}\n"

# Create temporary config with RAG disabled (workaround for API restrictions)
CONFIG_FILE="$OUTPUT_DIR/.egregora_config.yml"
cat > "$CONFIG_FILE" << 'EOF'
models:
  writer: google-gla:gemini-2.0-flash-exp
  enricher: google-gla:gemini-flash-latest
  embedding: google-gla:gemini-embedding-001

rag:
  enabled: false  # Disabled to avoid embedding API 403 errors

writer:
  enable_banners: false

pipeline:
  step_size: 50
  step_unit: messages
EOF

echo -e "${YELLOW}Configuration:${NC}"
cat "$CONFIG_FILE"
echo ""

# Set VCR recording mode
export PYTEST_RECORDING_MODE="once"  # Use "rewrite" to overwrite existing cassettes
export EGREGORA_CONFIG="$CONFIG_FILE"

echo -e "${GREEN}=== Running Egregora Pipeline with VCR Recording ===${NC}\n"

# Run the pipeline
# Note: Currently blocked by UUID serialization issue, but will record
# all API calls up to that point
uv run egregora write "$TEST_ZIP" --output="$OUTPUT_DIR" 2>&1 | tee "$OUTPUT_DIR/run.log"

EXIT_CODE=${PIPESTATUS[0]}

echo -e "\n${GREEN}=== Recording Summary ===${NC}\n"

# Check for created cassettes
CASSETTES_DIR="tests/cassettes"
if [ -d "$CASSETTES_DIR" ]; then
    CASSETTE_COUNT=$(find "$CASSETTES_DIR" -name "*.yaml" 2>/dev/null | wc -l)
    if [ "$CASSETTE_COUNT" -gt 0 ]; then
        echo -e "${GREEN}✓ Recorded $CASSETTE_COUNT VCR cassette(s):${NC}"
        find "$CASSETTES_DIR" -name "*.yaml" -exec ls -lh {} \;
    else
        echo -e "${YELLOW}⚠ No cassettes found in $CASSETTES_DIR${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Cassettes directory not found${NC}"
fi

# Check output
if [ -d "$OUTPUT_DIR" ]; then
    echo -e "\n${GREEN}Output files:${NC}"
    find "$OUTPUT_DIR" -type f | head -20
fi

# Final status
echo -e "\n${GREEN}=== Final Status ===${NC}\n"

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Pipeline completed successfully!${NC}"
    echo -e "\nNext steps:"
    echo "  1. Review cassettes in $CASSETTES_DIR"
    echo "  2. Commit cassettes to git: git add tests/cassettes/"
    echo "  3. Run tests without API key: unset GOOGLE_API_KEY && uv run pytest tests/"
else
    echo -e "${YELLOW}⚠ Pipeline exited with code $EXIT_CODE${NC}"
    echo -e "\nKnown issues:"
    echo "  • UUID serialization error (blocking writer agent)"
    echo "  • API key restrictions (403 errors on embedding API)"
    echo -e "\nCassettes were still recorded for successful API calls."
    echo -e "\nTo fix UUID issue:"
    echo "  1. Cast UUIDs to strings at IR table creation in src/egregora/database/validation.py"
    echo "  2. Or configure DuckDB to serialize UUIDs as strings"
    echo -e "\nTo fix API restrictions:"
    echo "  1. Go to Google Cloud Console → Credentials"
    echo "  2. Edit API key → Remove Application Restrictions"
    echo "  3. Or create a new unrestricted key for testing"
fi

echo -e "\nLog saved to: $OUTPUT_DIR/run.log"
