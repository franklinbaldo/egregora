# Plan: Enforce 100% Static Typing with Mypy and Pytest

## Goals
- Integrate `mypy` into the tooling stack and gate test runs on clean type checks.
- Ensure every function signature across the codebase is fully typed (no implicit `Any`).
- Prevent nested type expressions; whenever nesting would be required, define a named type alias instead.

## Proposed Work Breakdown

1. **Add mypy dependency and configuration**
   - Declare `mypy` and supporting plugins (e.g., `pytest-mypy` for tight pytest integration) in `pyproject.toml` under development dependencies managed by `uv`.
   - Create a `[tool.mypy]` section configured for strict typing: enable `disallow_untyped_defs`, `disallow_incomplete_defs`, `disallow_any_generics`, `warn_unused_ignores`, and `strict_optional`.
   - Define explicit `mypy_path` entries so imports resolve consistently in all environments.

2. **Introduce a pytest guard for type coverage**
   - Configure `pytest.ini` or `pyproject.toml` to automatically invoke mypy through `pytest --mypy` or a custom pytest plugin.
   - Ensure the pytest run fails whenever mypy finds untyped or partially typed definitions, thereby enforcing 100% typed code as part of the test suite.

3. **Audit and annotate the existing codebase**
   - Run `uv run pytest --mypy` (or `uv run mypy`) to collect all current typing violations.
   - Add missing type hints to function signatures, class attributes, and public interfaces to satisfy the strict mypy configuration.
   - Replace implicit `Any` usage with concrete types, introducing `TypedDict`, `Protocol`, or `dataclasses` where beneficial for clarity.

4. **Eliminate nested type literals**
   - Implement a lightweight static check (e.g., a custom pytest collection hook or a separate `uv run python -m scripts.check_type_aliases`) that walks the AST looking for nested `typing` constructs such as `list[dict[str, int]]`.
   - Whenever nesting is detected, refactor the code to define a new `TypeAlias` (e.g., `UserIdMap = dict[str, int]`) and use the alias in higher-level annotations.
   - Document the convention in the contributor guide to set expectations for future code.

5. **Automate the workflow**
   - Update project documentation (README or contributing guide) with instructions for running the new typing checks via `uv`.
   - Add a CI step that executes `uv run pytest --mypy` to guarantee the typing requirements remain enforced in continuous integration.

## Risks and Mitigations
- **High volume of required annotations**: Prioritize modules with the most runtime usage and update iteratively, merging frequently to avoid large, risky diffs.
- **False positives from the no-nested-types rule**: Clearly specify exemptions (e.g., third-party stubs) and allow the checker to skip generated code paths.
- **Developer friction**: Provide examples and templates for common type aliases to reduce confusion when nesting might otherwise be more concise.

## Success Criteria
- `uv run pytest` (with mypy integration) exits with status 0 on a clean checkout.
- The repository contains no untyped function definitions as reported by mypy.
- The custom nested-type checker produces zero findings.
- Documentation communicates the new typing expectations and workflows.
