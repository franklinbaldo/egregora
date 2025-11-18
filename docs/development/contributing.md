# Contributing

We welcome contributions to Egregora! This guide will help you get started with development.

## Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/your-fork/egregora.git
   cd egregora
   ```

2. Set up the development environment:
   ```bash
   # Create virtual environment
   uv venv
   source .venv/bin/activate
   
   # Install in development mode
   uv pip install -e ".[dev]"
   ```

3. Install pre-commit hooks (optional but recommended):
   ```bash
   pre-commit install
   ```

## Code Style

Egregora follows these conventions:

- **Formatting**: Use `black` for code formatting
- **Linting**: Use `ruff` for linting
- **Type hints**: All public functions should be typed
- **Documentation**: All public functions should have docstrings in Google format

Run formatting and linting:
```bash
# Format code
black .

# Lint code
ruff check .
```

## TENET-BREAK Philosophy

All contributions should align with Egregora's core principles:

- **Privacy First**: Personal data never leaves the user's machine unnecessarily
- **Local Processing**: All sensitive operations happen offline
- **Transparency**: Clear about what data is processed where
- **User Control**: Users have full control over their data and settings

## Architecture Layers

Egregora follows a three-layer architecture:

### 1. Input/Output Layer
- Input adapters: Parse data from various sources
- Output adapters: Format data for various destinations
- Protocol interfaces: Define common interfaces

### 2. Processing Layer  
- Privacy: PII detection and anonymization
- Enrichment: AI-powered analysis
- Transformations: Functional data transforms
- Storage: Database operations

### 3. Orchestration Layer
- CLI: Command-line interface
- Pipeline: Coordinating processing stages
- Configuration: Managing settings

## Adding New Features

When adding new features:

1. **Follow the architecture**: Place code in the appropriate layer
2. **Maintain privacy**: Ensure PII doesn't leak to external services
3. **Write tests**: Include unit and integration tests
4. **Update documentation**: Add to relevant documentation pages
5. **Consider performance**: Optimize for reasonable processing times

## Pull Request Process

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Add tests for new functionality
4. Update documentation as needed
5. Run the test suite: `pytest`
6. Submit a pull request with a clear description

## Code of Conduct

Please follow our Code of Conduct in all interactions. We are committed to providing a welcoming and inclusive environment for all contributors.