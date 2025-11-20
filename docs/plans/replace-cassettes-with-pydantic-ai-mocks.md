# Plan: Replace VCR Cassettes with Pydantic-AI Test Models

## Goal
Remove our dependency on recorded HTTP cassettes for LLM and embedding calls by switching to deterministic mocks implemented with Pydantic-AI `TestModel` classes (and equivalent embedding stubs). This gives us hermetic tests that:

- run offline without stored traffic,
- describe expectations in code instead of brittle YAML fixtures,
- and are easier to update alongside prompt/template changes.

## Why this matters
- **Cassettes are brittle**: every prompt tweak requires re-recording huge YAML payloads, creating noisy diffs and masking real regressions.
- **Security & privacy**: removing captured traffic reduces the risk of leaking secrets or message content.
- **Determinism**: `TestModel` lets us enumerate exact tool calls / responses, so we can validate logic paths rather than captured text blobs.

## Work Plan

1. **Inventory cassette usage**
   - Audit `tests/cassettes/` and map each cassette-driven test to the code paths it exercises (reader agent, writer agent, enrichment, etc.).
   - Tag each test with the LLM + embedding behaviors it requires (e.g., single response, multi-turn tool calls, embeddings of specific strings).

2. **Define canonical mock behaviors**
   - For every unique interaction pattern, author a `pydantic_ai.models.test.TestModel` subclass (or factory) that returns the structure those tests expect.
   - For embeddings, add a lightweight `MockEmbeddingModel` that deterministically hashes input text into fixed-length vectors (no network call).
   - Document these behaviors in `tests/README.md` so contributors know which fake to use.

3. **Extend pytest fixtures**
   - Update `tests/conftest.py` to expose fixtures like `test_writer_model`, `test_reader_model`, `mock_embeddings`.
   - Ensure fixtures mirror the production interfaces (`genai.Client`, `VectorStore`, etc.) so the pipeline code can swap them without conditional logic.

4. **Refactor targeted tests**
   - For each cassette-backed test suite:
     1. Replace the VCR decorator/fixture with the new mock fixtures.
     2. Assert against structured outputs (e.g., `PostComparison`, JSON metadata) rather than raw strings captured in YAML.
     3. Remove cassette files once the test is green with mocks.

5. **Clean up VCR infrastructure**
   - Delete VCR configuration files, helper utilities, and dependencies from `pyproject.toml`.
   - Update developer docs to describe the new mocking approach.

6. **Add guardrails**
   - Introduce a lint/test that fails if new cassette files are added (e.g., pytest check that `tests/cassettes` is empty).
   - Consider a pytest plugin or fixture that raises if code tries to hit the live Gemini client during tests.

7. **Final verification**
   - Run the full test suite to ensure no path still references VCR.
   - Capture before/after metrics (test runtime, flakiness reports) to validate the improvement.

## Deliverables
- Updated tests using Pydantic-AI mocks.
- Deleted cassette files and VCR dependencies.
- Documentation outlining how to author deterministic model/embedding responses.
- CI safeguard preventing reintroduction of cassettes.

This plan keeps the behavioral fidelity of our current e2e tests while removing the maintenance burden of recorded HTTP fixtures.
