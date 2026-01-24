# Contributing to Egregora

First off, thank you for considering contributing to Egregora! It's people like you that make this tool "magical".

## 🛡️ Security Vulnerabilities

If you discover a security vulnerability, please refer to our [Security Policy](SECURITY.md) for reporting instructions.

## 🐞 Reporting Bugs

We use GitHub Issues to track public bugs. Report a bug by opening a new issue; it's that easy!

## 🛠️ Development Setup

Egregora uses `uv` for dependency management and Python 3.12+.

1.  **Install `uv`**: Follow instructions at [astral.sh/uv](https://github.com/astral-sh/uv).
2.  **Clone the repository**:
    ```bash
    git clone https://github.com/franklinbaldo/egregora.git
    cd egregora
    ```
3.  **Install dependencies**:
    ```bash
    uv sync --all-extras
    ```
4.  **Install pre-commit hooks**:
    ```bash
    uv run pre-commit install
    ```

## 🚀 Pull Request Process

We follow the workflow defined in [Code of the Weaver](CLAUDE.md):

1.  **Create a branch**: `git checkout -b feature/your-feature`
2.  **Make changes**: Follow the [Code Standards](CLAUDE.md#code-standards).
3.  **Run tests**:
    ```bash
    uv run pytest tests/
    ```
4.  **Run pre-commit**:
    ```bash
    uv run pre-commit run --all-files
    ```
5.  **Commit**: Use descriptive commit messages (see format below).
6.  **Push**: `git push origin feature/your-feature`
7.  **Open PR**: Describe changes and link issues.

### Commit Message Format

```
<type>: <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring
- `test`: Adding/updating tests
- `docs`: Documentation changes
- `chore`: Maintenance tasks

## 📜 Coding Standards

Please refer to [CLAUDE.md](CLAUDE.md) for our detailed coding standards, including:
- Style Guide (Ruff, Black)
- Naming Conventions
- Error Handling
- Testing Philosophy

## 🤝 Community

Join the conversation in [GitHub Discussions](https://github.com/franklinbaldo/egregora/discussions).
