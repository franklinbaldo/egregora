# Contributing to Egregora

Thank you for your interest in contributing to Egregora! We welcome contributions from everyone, whether you're fixing a bug, improving documentation, or proposing a new feature.

## 🤝 Code of Conduct

This project is committed to providing a welcoming and inspiring community for all. By participating in this project, you agree to abide by our Code of Conduct.

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**: Ensure you have a compatible Python version installed.
- **uv**: We use [uv](https://github.com/astral-sh/uv) for dependency management.
- **Google Gemini API Key**: Required for running the AI agents (free tier available).

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/franklinbaldo/egregora.git
    cd egregora
    ```

2.  **Install dependencies**:
    ```bash
    uv sync --all-extras
    ```

3.  **Install pre-commit hooks**:
    ```bash
    uv run pre-commit install
    ```

4.  **Set up environment variables**:
    ```bash
    export GOOGLE_API_KEY="your-api-key"
    ```

## 🛠️ Development Workflow

### Branching Strategy

- **`main`**: The stable branch. Do not commit directly to `main`.
- **Feature Branches**: Create a new branch for your work:
    ```bash
    git checkout -b feature/your-feature-name
    ```

### Making Changes

1.  **Read the documentation**: Familiarize yourself with [`CLAUDE.md`](https://github.com/franklinbaldo/egregora/blob/main/CLAUDE.md) for coding standards and architecture details.
2.  **Make small, atomic commits**: Each commit should do one thing well.
3.  **Write tests**: Ensure your changes are covered by tests.
4.  **Follow the style guide**: We use Ruff for linting and formatting.

## 🧪 Testing

Run the test suite to ensure your changes don't break existing functionality:

```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=egregora
```

## 📝 Pull Request Process

1.  **Push your branch**: `git push origin feature/your-feature-name`
2.  **Open a Pull Request**: Provide a clear title and description of your changes.
3.  **Link Issues**: If your PR fixes an issue, link it (e.g., "Fixes #123").
4.  **Wait for Review**: A team member (or Jules persona) will review your PR.
5.  **Address Feedback**: Make necessary changes based on the review.

## 📜 Documentation Standards

- **Examples**: All code examples in documentation must be copy-paste-runnable.
- **Verification**: Run `uv run mkdocs build` to verify documentation changes locally.
- **Spelling**: We use `codespell` to check for spelling errors.

## 🧩 Architecture Decisions

Significant architectural changes require an ADR (Architecture Decision Record). See [`docs/adr/`](https://github.com/franklinbaldo/egregora/tree/main/docs/adr/) for existing records and [`docs/adr/template.md`](https://github.com/franklinbaldo/egregora/blob/main/docs/adr/template.md) for the template.

---

For more detailed technical guidelines, please refer to [`CLAUDE.md`](https://github.com/franklinbaldo/egregora/blob/main/CLAUDE.md).
