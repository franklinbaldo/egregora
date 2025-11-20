# Plan: Replace VCR Cassettes with Pydantic-AI Test Doubles

## Background & Intent
- Current integration tests still lean on pytest-vcr recordings for Gemini + embedding APIs, which are brittle, large, and tie us to legacy SDK request formats.
- Pydantic-AI already ships `TestModel` hooks that let us encode expected request/response transcripts directly in Python, including tool calls and binary attachments.
- Goal: eliminate cassette files entirely by migrating remaining suites (writer, enricher, embeddings) to deterministic mocks implemented via Pydantic-AI classes and stub embedding providers.

## Guiding Principles
1. **Deterministic transcripts**: encode agent messages + tool invocations as structured data so test skips network and asserts full conversation ordering.
2. **Ergonomic fixtures**: wrap TestModel definitions inside pytest fixtures so suites can `parametrize` behaviors (success, throttling, PII redaction) without re-recording.
3. **Binary payload support**: represent media/embedding bytes via helper dataclasses (e.g., `MockBinaryContent`) rather than touching filesystem.
4. **Documentation-first**: teach contributors how to extend mocks via README snippets + doctests before deleting cassette directories.

## Execution Steps
1. **Inventory remaining cassette users**
   - `rg 'pytest.mark.vcr'` + `tests/cassettes/` contents to map suites still relying on recordings.
   - Categorize by agent (writer/enricher/ranker) and by API (chat vs embeddings).
2. **Introduce TestModel base fixtures**
   - Create `tests/fixtures/pydantic_test_models.py` exposing reusable mock agents for writer + enricher + avatar flows.
   - Encode canonical transcripts (inputs, outputs, tool calls) as Pydantic models to remove YAML dependency.
3. **Mock embeddings deterministically**
   - Implement lightweight embedding stub class that hashes input chunk text → fixed float vectors.
   - Wire stub into `EnrichmentRuntimeContext` / RAG fixtures via dependency injection, documenting expected shape.
4. **Port suites incrementally**
   - Replace cassette markers with fixture-provided TestModels; assert on structured outputs instead of recorded HTTP payloads.
   - Delete cassette files per suite once equivalent mock coverage exists.
5. **Add safety net tests**
   - New regression test that fails if any `tests/cassettes/` YAML remains, ensuring future contributions adopt Pydantic-AI mocks (we already added guard but keep it updated).
6. **Document workflow**
   - Update `docs/testing/README.md` + `README.md` testing section with instructions on extending TestModels and embedding stubs.
   - Provide example snippet for binary/media enrichment mocking (using `BinaryContent` in-memory).

## Risks & Mitigations
- *Risk*: Divergence between mock transcripts and real API behavior.
  - **Mitigation**: Keep a single `golden_run.md` transcript recorded manually for reference and add smoke CLI scenario to verify live agent occasionally.
- *Risk*: Developers unsure how to extend mocks for new tools.
  - **Mitigation**: Provide template factory + pytest fixture for adding new tool responses by overriding dataclasses.

## Definition of Done
- No `.yaml` cassette files tracked; guard test passes.
- All suites previously decorated with `@pytest.mark.vcr` run using Pydantic-AI TestModels or deterministic stubs.
- Docs clearly describe how to author/extend mocks, and CI enforces cassette-free policy.
