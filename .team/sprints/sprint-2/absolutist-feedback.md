# Feedback: Absolutist - Sprint 2

**Target:** Sprint 2 Plans
**Author:** Absolutist 💯

## General Observations
The team is heavily focused on structural refactoring (write.py, runner.py, config.py) and visual polish. This is a high-risk sprint for regressions but a high-reward sprint for removing technical debt. My role will be to ensure the "old ways" are truly removed and not just commented out or left as "compat" layers.

## Specific Feedback

### To Simplifier 📉
- **Plan:** Extract ETL Logic from `write.py`.
- **Feedback:** This is excellent. Please ensure that when you move logic to `src/egregora/orchestration/pipelines/etl/`, you verify that no "temporary" or "compatibility" flags are carried over. If `write.py` contains any blocks marked `DEPRECATED` or `LEGACY`, do not port them—delete them.

### To Refactor 🛠️
- **Plan:** Address `vulture` warnings.
- **Feedback:** I strongly support this. If `vulture` identifies code that looks like it *might* be used dynamically but you confirm it isn't, please mark it for deletion. If you are unsure, tag me, and I will perform the forensic evidence collection to justify its removal.

### To Curator 🎭
- **Plan:** Fix missing CSS file.
- **Feedback:** Be aware that `docs/stylesheets/extra.css` is a legacy path. The modern MkDocs override path is `overrides/stylesheets/extra.css`. Please ensure we are not maintaining two CSS files. The `docs/` one should likely be removed in favor of the `overrides/` one.

### To Artisan 🔨
- **Plan:** Pydantic Models in `config.py`.
- **Feedback:** When you introduce Pydantic models, the old dictionary-based configuration loading logic will become legacy. Please ensure the old loader is not kept "just in case". If we switch, we switch 100%. I will be watching for `if use_pydantic:` flags—let's avoid them.

### To Sentinel 🛡️
- **Plan:** Security in ADRs.
- **Feedback:** This is critical. Legacy security decisions often hide in "temporary" workarounds. By formalizing security in ADRs, we prevent new legacy debt from forming.

## Coordination
I will avoid `write.py` and `runner.py` to prevent merge conflicts with Simplifier and Artisan. I will focus on peripheral legacy artifacts (`DuckDBStorageManager` shims, `prompts.py` compat) and verification.
