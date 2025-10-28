# Real Scenario Test Plan: WhatsApp Conversation Parsing & Manipulation

## Overview
This plan defines how to exercise Egregora against the **`tests/Conversa do WhatsApp com Teste.zip`** fixture introduced in this PR. The objective is to validate the end-to-end parsing of a real Portuguese WhatsApp export and the downstream manipulation steps that reshape the conversation into anonymized, article-ready content. The scenarios emphasize realistic user flows, data integrity, and resilience when handling mixed media (text plus images) and temporal metadata. Each section below ties expected behaviour back to concrete commands, code paths, and observable artefacts so the team can execute or automate the checks without guesswork.

## Artifacts Under Test
- **Zip archive**: `tests/Conversa do WhatsApp com Teste.zip`
  - `Conversa do WhatsApp com Teste.txt` — WhatsApp textual export containing system events, participant joins/leaves, and media placeholders.
  - `IMG-20251028-WA0035.jpg`, `IMG-20251027-WA0023.jpg`, `IMG-20251028-WA0033.jpg`, `IMG-20251028-WA0034.jpg` — Inline media referenced in the transcript.

## Execution Workflow at a Glance
```mermaid
graph TD
    A[tests/Conversa do WhatsApp com Teste.zip] --> B[uv run egregora process tests/Conversa do WhatsApp com Teste.zip --output=/tmp/egregora-real --timezone=America/Sao_Paulo --debug]
    B --> C[Parser events (egregora.parser.load_whatsapp_export)]
    C --> D[Anonymization (egregora.anonymizer.apply_pseudonyms)]
    D --> E[Manipulation pipeline (egregora.pipeline.process_whatsapp_export)]
    E --> F[Gemini reactions & cache (.egregora-cache/<site>)]
    F --> G[Article/export build (/tmp/egregora-real/docs/posts/)]
    G --> H[Regression Assertions (tests/test_whatsapp_real_scenario.py)]
```

## Environment Preparation & Tooling
1. **Bootstrap dependencies**
   ```bash
   uv sync
   ```
2. **Verify locale support** – run `uv run python -c "import locale; locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')"`. If unavailable, document the fallback locale (e.g. `pt_PT.UTF-8`) in test notes.
3. **Prime CLI context** – export `GOOGLE_API_KEY` and clean caches before every run:
   ```bash
   export GOOGLE_API_KEY=your-gemini-key
   rm -rf .egregora-cache && mkdir -p .egregora-cache
   ```
4. **Create scratch directories** – `rm -rf /tmp/egregora-real && mkdir -p /tmp/egregora-real` for CLI outputs and `mkdir -p /tmp/egregora-real-media` for isolated media extraction tests.
5. **Enable debug logging capture** – execute pipeline commands as `uv run egregora process ... --debug | tee /tmp/egregora-real/pipeline.log` to persist detailed Rich logs for later inspection.

## Test Data Preparation
1. Confirm fixture integrity before each run:
   ```bash
   shasum -a 256 tests/Conversa\ do\ WhatsApp\ com\ Teste.zip
   unzip -l tests/Conversa\ do\ WhatsApp\ com\ Teste.zip
   ```
2. Reuse `egregora.zip_utils.validate_zip_contents` inside a short Python snippet to gate tests:
   ```bash
   uv run python - <<'PY'
   import zipfile
   from egregora.zip_utils import validate_zip_contents

   with zipfile.ZipFile('tests/Conversa do WhatsApp com Teste.zip') as zf:
       validate_zip_contents(zf)
   print('zip validation ok')
   PY
   ```
3. Track extracted payloads with deterministic locations under `/tmp/egregora-real/.fixtures/` to simplify assertions for integration tests.

## Scenario Matrix
| Scenario | Objective | Steps (command-first) | Expected Outcomes | Instrumentation & Evidence |
| --- | --- | --- | --- | --- |
| **S1. Zip Intake Smoke Test** | Verify the ingest service can detect and unpack the archive safely. | 1. `uv run egregora process tests/Conversa\ do\ WhatsApp\ com\ Teste.zip --output=/tmp/egregora-real --timezone=America/Sao_Paulo --debug --period=day --no-enable-enrichment`.<br>2. Inspect `/tmp/egregora-real/.egregora/tmp` for extracted members.<br>3. Call `validate_zip_contents` inside a pytest fixture to fail fast on malformed archives. | - Archive recognized as WhatsApp export.<br>- All five files extracted with preserved names.<br>- Parser receives absolute paths for text and media. | - Archive Rich logs via `/tmp/egregora-real/pipeline.log`.<br>- Persist pytest snapshot of extraction manifest generated with `zipfile.ZipFile.namelist()`. |
| **S2. Header & System Message Parsing** | Ensure system messages and settings changes are captured with correct metadata. | 1. Run `uv run python -m pytest tests/test_whatsapp_real_scenario.py::test_system_events` (new test).<br>2. Within the test, invoke `parse_export` to obtain the `ibis.Table` and filter `event_type == 'system'`.<br>3. Compare timezone conversions against `America/Sao_Paulo` offsets using `table.mutate(local_time=...)`. | - Parser emits structured events for system lines.<br>- Timezone offsets correctly inferred from locale.<br>- Actor `Você` mapped to deterministic anonymized ID. | - Store filtered rows as CSV via `table.execute().to_csv('artifacts/system_events.csv')`.<br>- Attach CLI Rich table screenshot when anomalies occur. |
| **S3. Participant Message Extraction** | Validate standard messages with minimal content (empty lines after colon) are preserved. | 1. Execute `uv run python -m pytest tests/test_whatsapp_real_scenario.py::test_message_payloads`.<br>2. Query the `ibis.Table` for Franklin's messages around `2025-10-28T14:09:00` and ensure blank payload rows persist.<br>3. Cross-check sequence numbers in generated Markdown drafts under `/tmp/egregora-real/docs/posts/`. | - Empty/whitespace payloads stored as explicit entries with correct anonymized sender.<br>- Sequence numbers reflect original order.<br>- No unintended merging of consecutive messages. | - Export query results to `artifacts/s3_messages.csv` via pandas.<br>- Capture CLI diff using `pytest --maxfail=1 -vv` on failure. |
| **S4. Media Placeholder Handling** | Confirm attachments referenced in text map to actual files. | 1. Inside tests, call `extract_and_replace_media` to receive `media_mapping` and assert every placeholder resolves to a file under `docs/media/`.<br>2. Hash each extracted image with `shasum -a 256 /tmp/egregora-real/docs/media/**/*.jpg`.<br>3. Load images via Pillow (`from PIL import Image`) to assert width/height metadata for regression snapshots. | - Media events include checksum, MIME type, and relative path.<br>- Missing file detection raises actionable errors.<br>- Successful decode of image dimensions for downstream enrichment. | - Archive mapping as JSON (`artifacts/media_mapping.json`).<br>- Emit pytest JUnit attachments for Pillow dimension checks. |
| **S5. Date Range & Session Segmentation** | Test timeline segmentation across multi-day gaps. | 1. Use `group_by_period` to materialize per-day tables, then compute 6-hour breakpoints inside pytest using pandas `diff()` on timestamps.<br>2. Assert counts via `uv run python -m pytest tests/test_whatsapp_real_scenario.py::test_session_segmentation`. | - Distinct sessions produced for system setup vs. conversation burst.<br>- Summaries include correct participant roster and message counts.<br>- No off-by-one errors in session boundaries. | - Commit segmentation summary as CSV under `artifacts/session_summary.csv`.<br>- Track runtime drift with `pytest --durations=5`. |
| **S6. Data Sanitization & Anonymization** | Ensure personal identifiers are obfuscated before manipulation. | 1. Inspect the anonymized sender UUIDs returned by `parse_export` (`df.select(df.sender_uuid).distinct()`).<br>2. Execute `uv run python -m pytest tests/test_whatsapp_real_scenario.py::test_anonymization` to assert no raw names remain in generated Markdown/posts. | - Deterministic pseudonyms generated per participant.<br>- Media references replaced with sanitized tokens.<br>- Original names absent from downstream artifacts. | - Store anonymized participant snapshot in `tests/__snapshots__/test_anonymization`. |
| **S7. Content Manipulation Pipeline** | Exercise summarization/threading operations on sanitized data. | 1. Run full CLI with enrichment enabled into a fresh directory: `uv run egregora process tests/Conversa\ do\ WhatsApp\ com\ Teste.zip --output=/tmp/egregora-real-enriched --timezone=America/Sao_Paulo --debug --period=day`.<br>2. Execute `uv run python -m pytest tests/test_whatsapp_real_scenario.py::test_article_structure` while monkeypatching `egregora.genai_utils.call_gemini` to return deterministic payloads. | - Pipeline tolerates sparse content without crashing.<br>- Summary highlights disappearing-message policy change and media attachments.<br>- Output meets formatting and localization expectations. | - Collect generated Markdown under `artifacts/articles/` for manual review.<br>- Diff cached vs. mocked Gemini responses in pytest logs. |
| **S8. Gemini Reaction Generation & Caching** | Validate that agent reactions generated via Gemini are cached and reused. | 1. Clear cache (`rm -rf .egregora-cache && mkdir -p .egregora-cache`).<br>2. Instrument `google.genai.GenerativeModel.generate_content` in pytest to increment a counter.<br>3. Run pipeline twice and assert the second run reads from cache without extra API calls. | - Gemini calls succeed with authenticated requests.<br>- Cache entries include prompt hash, timestamp, and response metadata.<br>- Second execution reuses cached payloads, reducing latency and API usage without altering outputs. | - Record call counts in `artifacts/cache_metrics.json`.<br>- Compare runtime between runs to quantify cache benefit. |
| **S9. Round-trip Export Validation** | Confirm manipulated content can be exported without losing traceability. | 1. Use the dict returned by `process_whatsapp_export` to dump JSON timeline snapshots per period.<br>2. Feed export back into a validator helper that rebuilds message ordering and verifies media token resolution. | - Export retains message ordering and linkages.<br>- Media tokens resolvable to sanitized asset store.<br>- Importer can reconstruct timeline matching original counts. | - Store export JSON and validation report under `artifacts/round_trip/`.<br>- Track coverage via `pytest --cov=egregora.pipeline`. |
| **S10. Error Injection & Recovery** | Test robustness against corrupted media or truncated transcript. | 1. Remove one image (`zip -d` or rename) and rerun CLI expecting warning not crash.<br>2. Truncate transcript after first media placeholder, rerun, and capture exit code via `$?`.<br>3. Execute `uv run python -m pytest tests/test_whatsapp_errors.py::test_recovery_paths` that monkeypatches filesystem failures. | - Missing media triggers descriptive, non-fatal warnings where possible.<br>- Truncated transcript results in partial parse with clear error reporting.<br>- Pipeline surfaces actionable remediation steps. | - Store stderr from failure runs under `artifacts/error_logs/`.<br>- Ensure pytest asserts on exception types (`ZipValidationError`, `ValueError`). |

## Manual Validation Checklist
- [ ] Execute the helper snippet below to dump system events and confirm expected row counts using `ibis` → pandas conversion.
- [ ] Run `rg "Franklin" /tmp/egregora-real -n` and ensure no real names leak post-anonymization.
- [ ] Verify `.egregora-cache` contains Gemini payload directories with `v1` metadata files.
- [ ] Open generated posts under `/tmp/egregora-real/docs/posts/` to ensure Portuguese accents render correctly in Markdown.
- [ ] Check `/tmp/egregora-real/pipeline.log` for cache-hit messages on the second execution.
- [ ] Ensure regression tests exist under `tests/test_whatsapp_real_scenario.py` with descriptive docstrings referencing this plan.

## Helper Snippets
Reuse these snippets to collect evidence quickly during manual or automated runs.

### Dump system events to CSV
```bash
uv run python - <<'PY'
from datetime import date
from pathlib import Path

import pandas as pd

from egregora.models import WhatsAppExport
from egregora.parser import parse_export
from egregora.pipeline import discover_chat_file
from egregora.types import GroupSlug

zip_path = Path('tests/Conversa do WhatsApp com Teste.zip')
group_name, chat_file = discover_chat_file(zip_path)
export = WhatsAppExport(
    zip_path=zip_path,
    group_name=group_name,
    group_slug=GroupSlug(group_name.lower().replace(' ', '-')),
    export_date=date.today(),
    chat_file=chat_file,
    media_files=[],
)

table = parse_export(export)
system_rows = table.filter(table.event_type == 'system').execute()
Path('artifacts').mkdir(exist_ok=True)
system_rows.to_csv('artifacts/system_events.csv', index=False)
print(system_rows[['timestamp', 'sender_uuid', 'payload']])
PY
```

### Summarize session segmentation
```bash
uv run python - <<'PY'
from datetime import date
from pathlib import Path

import pandas as pd

from egregora.models import WhatsAppExport
from egregora.parser import parse_export
from egregora.pipeline import discover_chat_file, group_by_period
from egregora.types import GroupSlug

zip_path = Path('tests/Conversa do WhatsApp com Teste.zip')
group_name, chat_file = discover_chat_file(zip_path)
export = WhatsAppExport(
    zip_path=zip_path,
    group_name=group_name,
    group_slug=GroupSlug(group_name.lower().replace(' ', '-')),
    export_date=date.today(),
    chat_file=chat_file,
    media_files=[],
)

table = parse_export(export)
periods = group_by_period(table, period='day')
rows: list[dict] = []
for period_key, period_table in periods.items():
    df = period_table.execute()
    rows.append(
        {
            'period': period_key,
            'message_count': len(df),
            'participants': sorted(df['sender_uuid'].unique()),
        }
    )

Path('artifacts').mkdir(exist_ok=True)
summary = pd.DataFrame(rows)
summary.to_csv('artifacts/session_summary.csv', index=False)
print(summary)
PY
```

## Automation Roadmap
1. **Fixture Loader Utility (`tests/conftest.py`)** – Add a `whatsapp_fixture(tmp_path)` fixture that unzips the archive, calls `validate_zip_contents`, and yields structured paths (text file, media dir, cache dir).
2. **Parser Integration Test (`tests/test_whatsapp_real_scenario.py`)** – Assert counts for system vs. participant events using `ibis` + pandas conversions, verify anonymized IDs, and snapshot `event.schema` to catch schema drift.
3. **Manipulation Regression (`tests/test_whatsapp_real_scenario.py::test_article_structure`)** – Use `pytest` plus a lightweight stub of `egregora.genai_utils.call_gemini` to replay deterministic Gemini responses while still exercising cache plumbing.
4. **Cache Consistency Check (`tests/test_gemini_cache.py`)** – Instrument `egregora.cache.EnrichmentCache` and monkeypatch the Gemini client to assert the second run performs zero network calls.
5. **Negative Case Suite (`tests/test_whatsapp_errors.py`)** – Parameterize corrupted media and truncated transcript inputs, expecting `ZipValidationError` or graceful warnings surfaced via Rich console captures.
6. **CI Integration (`.github/workflows/ci.yml`)** – Extend the workflow to run the new pytest subset under `uv run pytest -m "whatsapp_real"` and upload generated artefacts (`artifacts/`) for manual inspection on failure.
