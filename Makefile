.PHONY: help setup-dev install-hooks test lint format clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup-dev: ## Set up development environment (install deps + pre-commit hooks)
	@echo "📦 Installing dependencies with lint extras..."
	uv sync --extra lint --extra test
	@echo "🔧 Installing pre-commit hooks..."
	uv run pre-commit install
	@echo "✅ Development environment ready!"
	@echo "💡 Pre-commit hooks will now run automatically on git commit"

install-hooks: ## Install pre-commit hooks only
	@echo "🔧 Installing pre-commit hooks..."
	uv run pre-commit install
	@echo "✅ Pre-commit hooks installed!"

test: ## Run tests
	uv run pytest

lint: ## Run linting checks
	uv run pre-commit run --all-files

format: ## Format code
	uv run ruff format .
	uv run ruff check --fix .

clean: ## Clean up build artifacts and caches
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build dist .eggs
	@echo "✨ Cleaned up build artifacts and caches"
