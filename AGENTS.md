# Agent Guidelines

- Do not attempt to maintain backward compatibility with previous versions.
- Prioritize creating clean, organized, and maintainable code.
- Use `uv` for any project automation; run tests and tools via commands such as `uv run pytest`.
- The test suite requires DuckDB to be available. Ensure it is included with the testing dependencies and installed before executing tests.
