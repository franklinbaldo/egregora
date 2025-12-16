# 3. V3 Coexistence Strategy

Date: 2025-05-23

## Status

Accepted

## Context

The repository currently contains two distinct architectures: the stable current version (`src/egregora`) and the next-generation version (`src/egregora_v3`).

Concerns were raised that this duplication creates technical debt, confusion regarding where to apply fixes, and violations of DRY (Don't Repeat Yourself) principles due to shared concepts (templates, prompts) being implemented twice.

## Decision

We have decided to maintain `src/egregora_v3` as an intentional, isolated parallel development track. It is **not** considered "duplicate code" in the traditional sense of technical debt, but rather a staging ground for a complete architectural rewrite.

### Implications

1.  **Isolation:** `src/egregora_v3` will remain a distinct package structure. It should not be merged or entangled with the current `src/egregora` codebase until it is ready to replace it entirely.
2.  **Default Target for Refactoring:** Unless a task explicitly specifies "V3" or "Next Gen", all bug fixes, refactoring, and maintenance work must target the **current version** (`src/egregora`).
3.  **Acceptable Duplication:** We accept the temporary "duplication tax" (e.g., having similar template loading logic in both places) to allow V3 to evolve without being constrained by legacy compatibility or breaking the stable version.

## Consequences

*   **Pros:** Allows V3 to innovate freely without risking the stability of the current production system. Clear separation of concerns between "maintenance" and "R&D".
*   **Cons:** Fixes applied to shared concepts in V2 must be manually ported to V3 if relevant.
