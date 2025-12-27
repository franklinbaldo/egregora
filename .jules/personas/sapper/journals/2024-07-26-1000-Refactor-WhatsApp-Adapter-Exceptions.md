---
title: "💣 Structured Exceptions for WhatsApp Media Delivery"
date: 2024-07-26
author: "Sapper"
emoji: "💣"
type: journal
---

## 💣 2024-07-26 - Summary

**Observation:** The `deliver_media` method in `src/egregora/input_adapters/whatsapp/adapter.py` was violating the "Trigger, Don't Confirm" principle. It swallowed multiple types of errors (invalid paths, missing files, zip corruption) and returned `None`, forcing the caller to perform defensive checks and losing valuable failure context.

**Action:** I executed a full Test-Driven Development refactoring.
1.  **Identified Target:** Located the `WhatsAppAdapter` and confirmed the absence of a dedicated test file.
2.  **Established Hierarchy:** Created a new, specific exception hierarchy in `src/egregora/input_adapters/whatsapp/exceptions.py`, with `MediaDeliveryError` as a base and specific exceptions like `InvalidMediaReferenceError`, `MissingZipPathError`, `ZipPathNotFoundError`, `MediaNotFoundError`, and `MediaExtractionError`.
3.  **TDD (RED):** Created a new test file, `tests/unit/input_adapters/whatsapp/test_adapter.py`, and wrote a suite of failing tests, each asserting that one of the new exceptions was raised under the correct failure condition.
4.  **TDD (GREEN):** Refactored `deliver_media` and its helper methods to raise these specific exceptions instead of returning `None`. The function's return type hint was updated to `-> Document`, removing `| None`.
5.  **TDD (VERIFY):** Ran the test suite and confirmed all tests passed.

**Reflection:** This was a successful mission, hardening the WhatsApp adapter's media handling logic. The failure modes are now explicit, structured, and informative. The `parse` method in the same file still uses a broad `except WhatsAppParsingError`. While it correctly re-raises the exception, a future mission could investigate if more granular exceptions from the parsing module could be caught and wrapped here to provide even richer, adapter-level context to the orchestrator. For example, a `ConfigError` during parsing could be wrapped in an `AdapterConfigurationError`.
