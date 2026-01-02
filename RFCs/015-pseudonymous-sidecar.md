# RFC: Pseudonymous Sidecar
**Status:** Actionable Proposal
**Date:** 2024-07-26
**Disruption Level:** Medium - Fast Path

## 1. The Vision
This RFC proposes a new, optional "Pseudonymous Mode." When enabled, the ingestion adapter will replace raw author identifiers (e.g., phone numbers, names) with stable, non-identifiable pseudonyms (e.g., `Author_0x2a9e`, `Author_0x5b1f`). These pseudonyms will **only** be written to the structured data sidecar (`.json` file) and will **not** appear in the public-facing Markdown output. This gives the agent the critical concept of attribution, allowing it to understand *who* said *what*, which is the foundational prerequisite for the "Living Document" moonshot.

## 2. The Broken Assumption
This proposal challenges the assumption that **the only way to ensure privacy is through total anonymization.**

> "We currently assume that all user identifiers must be completely erased at the ingestion boundary. This provides strong privacy but prevents the agent from understanding conversational dynamics, attribution, or feedback. By introducing stable pseudonyms, we can enable these powerful features while still protecting user identity."

## 3. The First Implementation Path (≤30 days)
- **Step 1: Add Pseudonym Generation to Ingestion:** In the core ingestion logic, add an optional mode that, if enabled, creates a salted hash of the original author identifier to produce a consistent pseudonym (e.g., `sha256(salt + author_id)`). The mapping and salt should be ephemeral, existing only for the duration of a single pipeline run.
- **Step 2: Plumb Pseudonyms to the Writer Agent:** The `Entry` objects passed through the pipeline will now contain this pseudonym in their author field.
- **Step 3: Write Pseudonyms to JSON Sidecar:** Update the `MkDocsAdapter`'s persistence logic. The Markdown writer will continue to strip all author information. However, the JSON sidecar writer will now include a `participants` field containing the list of pseudonyms involved in the conversation.

## 4. The Value Proposition
This is the fastest and safest way to build momentum toward the "Living Document" vision.
- **Unlocks Attribution:** It provides the agent with the bare-minimum concept of identity needed to track speakers and eventually process targeted feedback.
- **Zero-Impact on Current Output:** The public-facing blog remains completely anonymous. This feature is purely additive and machine-readable, posing no risk to the existing user experience.
- **De-risks the Moonshot:** It proves we can create and persist attribution data before we invest in complex, two-way document synchronization adapters.

## 5. Success Criteria
- A new configuration flag in `egregora.toml` can enable `privacy.mode = "pseudonymous"`.
- When enabled, the `[post-slug].json` file contains a list of stable, unique pseudonyms.
- The `[post-slug].md` file remains fully anonymized, with no pseudonyms present.
