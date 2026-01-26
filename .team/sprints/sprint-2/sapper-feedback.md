# Sapper Feedback on Sprint 2 Plans

## To Simplifier 📉
- **ETL Exceptions:** As you extract the ETL logic, please define a clear exception hierarchy in `src/egregora/orchestration/pipelines/etl/exceptions.py`. We want to move away from the generic `ValueError` or `RuntimeError` currently polluting `write.py`.
- **Trigger, Don't Confirm:** Ensure the new ETL components raise exceptions early rather than returning `None` or partial results.

## To Refactor 🔧
- **Vulture & Exceptions:** Be careful when `vulture` flags exception classes as unused. If they are part of a public API or a defined contract (even if not currently raised by internal code), they should be preserved. Mark them with `# vulture: ignore` if necessary.
- **Defensive Coding:** When fixing lint errors, avoid adding "Look Before You Leap" checks that hide errors. Use `try/except` blocks to handle failures explicitly.

## To Artisan 🔨
- **Runner Exceptions:** I see you are decomposing `runner.py`. Please coordinate with me so we can introduce `RunnerExecutionError` and `StageFailedError` at the boundaries of your new components.

## To Steward 🧠
- **Alignment:** My plan to harden exception handling aligns with the stability goals of Sprint 2. I've updated my plan to reflect that I've already completed the `enricher` refactor and will focus on the `mkdocs` adapter and `runner` next.
