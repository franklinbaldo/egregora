# Real Scenario Test Plan: WhatsApp Conversation Parsing & Manipulation

## Overview
This plan defines how to exercise Egregora against the **`tests/Conversa do WhatsApp com Teste.zip`** fixture introduced in this PR. The objective is to validate the end-to-end parsing of a real Portuguese WhatsApp export and the downstream manipulation steps that reshape the conversation into anonymized, article-ready content. The scenarios emphasize realistic user flows, data integrity, and resilience when handling mixed media (text plus images) and temporal metadata.

## Artifacts Under Test
- **Zip archive**: `tests/Conversa do WhatsApp com Teste.zip`
  - `Conversa do WhatsApp com Teste.txt` — WhatsApp textual export containing system events, participant joins/leaves, and media placeholders.
  - `IMG-20251028-WA0035.jpg`, `IMG-20251027-WA0023.jpg`, `IMG-20251028-WA0033.jpg`, `IMG-20251028-WA0034.jpg` — Inline media referenced in the transcript.

## Test Environment & Tooling
1. Use the repository's recommended Python version (3.11+) and install dependencies via `uv sync`.
2. Ensure any locale-sensitive parsing utilities (e.g., `pt_BR` date parsing) are available.
3. Configure a writable temp directory for extracted media manipulation.
4. Provide a valid **Gemini API key** via environment variable so that LLM-backed reaction generation can be executed end-to-end.
5. Enable detailed logging for the parser and manipulation pipeline to capture edge cases observed during the scenarios, including LLM request/response metadata for cache validation.

## Scenario Matrix
| Scenario | Objective | Steps | Expected Outcomes |
| --- | --- | --- | --- |
| **S1. Zip Intake Smoke Test** | Verify the ingest service can detect and unpack the archive. | 1. Feed the zip file into the ingestion entry point (CLI or API).<br>2. Confirm extraction to a temporary workspace.<br>3. Pass extracted payload paths to the parser. | - Archive recognized as WhatsApp export.<br>- All five files extracted with preserved names.<br>- Parser receives absolute paths for both text and media. |
| **S2. Header & System Message Parsing** | Ensure system messages and settings changes are captured with correct metadata. | 1. Execute parser on the transcript file.<br>2. Inspect parsed events for the intro banner, group creation, participant add/remove, and disappearing message updates.<br>3. Validate timestamps and actor resolution. | - Parser emits structured events for system lines.<br>- Timezone offsets correctly inferred from locale.<br>- Actor `Você` mapped to deterministic anonymized ID. |
| **S3. Participant Message Extraction** | Validate standard messages with minimal content (empty lines after colon) are handled. | 1. Focus on Franklin's consecutive messages at `28/10/2025 14:09-14:10`.<br>2. Confirm blank content rows are not dropped or mis-attributed.<br>3. Ensure message grouping logic respects minute-level ordering. | - Even empty/whitespace payloads stored as explicit entries with correct author.<br>- Sequence numbers reflect original order.<br>- No unintended merging of consecutive messages. |
| **S4. Media Placeholder Handling** | Confirm attachments referenced in text map to actual files. | 1. Identify `IMG-20251028-WA0035.jpg` and related placeholders.<br>2. Cross-verify parser generates `media` events with file pointers.<br>3. Attempt to load each image for further processing. | - Media events include checksum, MIME type, and relative path.<br>- Missing file detection raises actionable errors.<br>- Successful decode of image dimensions for downstream enrichment. |
| **S5. Date Range & Session Segmentation** | Test timeline segmentation across multi-day gaps. | 1. Run session clustering on parsed events (gap threshold e.g., 6 hours).<br>2. Verify system banner (03/10) is separated from October 28 discussion.<br>3. Check metadata summarizing session duration and participants. | - Distinct sessions produced for system setup vs. conversation burst.<br>- Summaries include correct participant roster and message counts.<br>- No off-by-one errors in session boundaries. |
| **S6. Data Sanitization & Anonymization** | Ensure personal identifiers are obfuscated before manipulation. | 1. Feed parsed messages into anonymization stage.<br>2. Inspect outputs to confirm proper pseudonyms for `Franklin`, `Você`, `Iuri Brasil`.<br>3. Validate media filenames are hashed or remapped. | - Deterministic pseudonyms generated per participant.<br>- Media references replaced with sanitized tokens.<br>- Original names absent from downstream artifacts. |
| **S7. Content Manipulation Pipeline** | Exercise summarization/threading operations on sanitized data. | 1. Run topic clustering or article synthesis pipeline.<br>2. Focus on how empty/short messages influence clustering.<br>3. Generate final article draft and inspect structure. | - Pipeline tolerates sparse content without crashing.<br>- Summary highlights disappearing-message policy change and media attachments.<br>- Output meets formatting and localization expectations. |
| **S8. Gemini Reaction Generation & Caching** | Validate that agent reactions generated via Gemini are cached and reused. | 1. Configure Gemini credentials and trigger manipulation stage that requests agent reactions.<br>2. Capture first-run responses and persist them into the designated cache store.<br>3. Rerun the stage to ensure cache hits prevent duplicate API calls while yielding identical downstream artifacts. | - Gemini calls succeed with authenticated requests.<br>- Cache entries include prompt hash, timestamp, and response metadata.<br>- Second execution reuses cached payloads, reducing latency and API usage without altering outputs. |
| **S9. Round-trip Export Validation** | Confirm manipulated content can be exported without losing traceability. | 1. Produce an export package (markdown or JSON) from manipulated dataset.<br>2. Verify references back to original message IDs/media tokens.<br>3. Attempt to regenerate conversation timeline from export. | - Export retains message ordering and linkages.<br>- Media tokens resolvable to sanitized asset store.<br>- Importer can reconstruct timeline matching original counts. |
| **S10. Error Injection & Recovery** | Test robustness against corrupted media or truncated transcript. | 1. Temporarily remove one image and rerun pipeline.<br>2. Truncate the transcript after the first media placeholder and rerun.<br>3. Observe error messages and recovery behavior. | - Missing media triggers descriptive, non-fatal warnings where possible.<br>- Truncated transcript results in partial parse with clear error reporting.<br>- Pipeline surfaces actionable remediation steps. |

## Manual Validation Checklist
- [ ] All parsed events include localized timestamp parsing coverage.
- [ ] Attachments stored with checksum verification and deduplicated naming.
- [ ] Disappearing-message metadata propagated into manipulation stage for policy-aware summaries.
- [ ] Sanitized outputs verified against a PII scan to confirm no real names remain.
- [ ] Regression test cases added under `tests/` referencing this zip via fixture helpers.

## Automation Roadmap
1. **Fixture Loader Utility**: Implement a helper in `tests/` to unzip archives into temp dirs and yield structured paths for parsers.
2. **Parser Integration Test**: Use `pytest` to assert event counts, participant IDs, and media mapping for the provided transcript.
3. **Manipulation Regression Test**: Mock summarization/model calls where deterministic outputs are needed, but execute real Gemini calls behind a cache layer to validate request plumbing, retries, and persistence format.
4. **Cache Consistency Check**: Add assertions that Gemini reaction caches are hit on subsequent runs and that cache invalidation (e.g., prompt change) triggers fresh API calls without stale leakage.
5. **Negative Case Suite**: Parameterize corrupted media/truncated transcript scenarios to verify graceful degradation.
6. **CI Hook**: Wire these tests into existing workflows to prevent regressions when parser or manipulation logic evolves.
