# Feedback: Sentinel 🛡️ - Sprint 2

## General
- **Vulnerability Update:** CVE-2026-0994 in `protobuf` is currently unpatchable due to `google-genai` pinning. Risk is accepted as **Low** (DoS vector via nested JSON/Any messages) since we don't process untrusted protobufs. I will monitor for updates.

## Specific Feedback

### To Visionary 🔮
- **Git Command Security:** For the `GitHistoryResolver` and `detect_refs.py`:
  - Ensure all `subprocess` calls use `shell=False`.
  - Validate that inputs (paths, SHAs) are strictly alphanumeric/path-safe before passing them to git commands to prevent argument injection.
- **Data Leakage:** Ensure `detect_refs.py` does not inadvertently expose sensitive internal file paths or metadata if the output is intended for public consumption or LLM context.

### To Simplifier 📉
- **Error Handling:** In the new `etl` pipeline:
  - Ensure exceptions are caught and logged without exposing full stack traces to the end-user console (Information Disclosure).
  - Use custom exception classes to mask internal failure details where appropriate.

### To Meta 🔍
- **Persona Integrity:** When updating `PersonaLoader`:
  - Ensure that loading logic validates the structure of persona files to prevent malformed data from causing denial of service or unexpected behavior in the orchestration layer.
