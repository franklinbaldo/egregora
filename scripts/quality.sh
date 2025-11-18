#!/usr/bin/env bash
# Code quality checks for Egregora
#
# Replaces dev_tools/code_quality.py with simple shell script.
# Uses standard tools directly instead of custom orchestration.
#
# Usage:
#   scripts/quality.sh                    # Run all checks
#   scripts/quality.sh --quick            # Run only fast checks (ruff)
#   scripts/quality.sh --check <tool>     # Run specific check
#   scripts/quality.sh --ci               # CI mode (fail fast)

set -e  # Exit on first error in CI mode

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
QUICK_MODE=false
CI_MODE=false
SPECIFIC_CHECK=""
COVERAGE_THRESHOLD=40

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --ci)
            CI_MODE=true
            shift
            ;;
        --check)
            SPECIFIC_CHECK="$2"
            shift 2
            ;;
        --coverage-threshold)
            COVERAGE_THRESHOLD="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--quick] [--ci] [--check <tool>] [--coverage-threshold <n>]"
            exit 1
            ;;
    esac
done

# Helper function to run a check
run_check() {
    local name="$1"
    local emoji="$2"
    shift 2
    local cmd=("$@")

    if [[ -n "$SPECIFIC_CHECK" && "$SPECIFIC_CHECK" != "$name" ]]; then
        return 0
    fi

    echo -e "${BLUE}${emoji} Running ${name}...${NC}"

    if "${cmd[@]}"; then
        echo -e "${GREEN}✅ ${name} passed${NC}"
        return 0
    else
        local exit_code=$?
        echo -e "${RED}❌ ${name} failed (exit code: ${exit_code})${NC}"
        if [[ "$CI_MODE" == "true" ]]; then
            exit $exit_code
        fi
        return $exit_code
    fi
}

# Track overall status
FAILED_CHECKS=()

# Ruff (linting + formatting)
run_check "ruff" "🔍" uv run ruff check . || FAILED_CHECKS+=("ruff")

# Quick mode: only run ruff
if [[ "$QUICK_MODE" == "true" ]]; then
    if [[ ${#FAILED_CHECKS[@]} -eq 0 ]]; then
        echo -e "${GREEN}✅ All quick checks passed${NC}"
        exit 0
    else
        echo -e "${RED}❌ Failed checks: ${FAILED_CHECKS[*]}${NC}"
        exit 1
    fi
fi

# Complexity analysis (radon)
if command -v radon &> /dev/null || uv run radon --version &> /dev/null 2>&1; then
    run_check "radon" "📊" uv run radon cc src tests --min C --show-complexity || FAILED_CHECKS+=("radon")
else
    echo -e "${YELLOW}⚠️  radon not installed, skipping complexity check${NC}"
fi

# Dead code detection (vulture)
if command -v vulture &> /dev/null || uv run vulture --version &> /dev/null 2>&1; then
    run_check "vulture" "🧹" uv run vulture src tests --min-confidence 80 || FAILED_CHECKS+=("vulture")
else
    echo -e "${YELLOW}⚠️  vulture not installed, skipping dead code check${NC}"
fi

# Security scan (bandit)
if command -v bandit &> /dev/null || uv run bandit --version &> /dev/null 2>&1; then
    run_check "bandit" "🔒" uv run bandit -r src -ll || FAILED_CHECKS+=("bandit")
else
    echo -e "${YELLOW}⚠️  bandit not installed, skipping security scan${NC}"
fi

# Dependency check (deptry) - continue on error (many false positives)
if command -v deptry &> /dev/null || uv run deptry --version &> /dev/null 2>&1; then
    echo -e "${BLUE}📦 Running deptry...${NC}"
    if uv run deptry .; then
        echo -e "${GREEN}✅ deptry passed${NC}"
    else
        echo -e "${YELLOW}⚠️  deptry has warnings (not failing, known false positives)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  deptry not installed, skipping dependency check${NC}"
fi

# Test coverage (pytest-cov)
if [[ "$SPECIFIC_CHECK" == "" || "$SPECIFIC_CHECK" == "coverage" ]]; then
    echo -e "${BLUE}🧪 Running test coverage...${NC}"
    if uv run pytest --cov=egregora --cov-report=term-missing --cov-fail-under="$COVERAGE_THRESHOLD" tests/; then
        echo -e "${GREEN}✅ coverage passed (>= ${COVERAGE_THRESHOLD}%)${NC}"
    else
        echo -e "${RED}❌ coverage failed (< ${COVERAGE_THRESHOLD}%)${NC}"
        FAILED_CHECKS+=("coverage")
        if [[ "$CI_MODE" == "true" ]]; then
            exit 1
        fi
    fi
fi

# Summary
echo ""
echo "========================================"
if [[ ${#FAILED_CHECKS[@]} -eq 0 ]]; then
    echo -e "${GREEN}✅ All quality checks passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Failed checks: ${FAILED_CHECKS[*]}${NC}"
    exit 1
fi
