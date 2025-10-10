# Issue #018: Add Test Coverage Reporting to CI

- **Status**: Proposed
- **Type**: Developer Experience
- **Priority**: Medium
- **Effort**: Low

## Problem

Although the project has an established pytest suite, the CI workflow does not publish coverage metrics. Without visibility into coverage trends, it is difficult to judge how well critical code paths are protected when reviewing pull requests.

## Proposal

1. **Introduce coverage tooling.** Add `pytest-cov` as a development dependency and ensure it is available in the CI environment.
2. **Update GitHub Actions.** Modify `.github/workflows/ci.yml` to run `uv run --with pytest pytest --cov=src/egregora --cov-report=xml` so the pipeline produces a coverage report.
3. **Publish metrics.** Optionally integrate with Codecov or Coveralls by uploading `coverage.xml`, and add a badge to the README for quick visibility.
4. **Document expectations.** Note in the contributor guide that significant features should maintain or improve coverage.

## Expected Benefits

- Gives reviewers quantifiable insight into test completeness.
- Encourages contributors to add or extend tests.
- Helps identify untested modules for future work.

## Dependencies

- Minor updates to `pyproject.toml`/`uv.lock`.
- Credentials or configuration for the chosen coverage reporting service (if any).
