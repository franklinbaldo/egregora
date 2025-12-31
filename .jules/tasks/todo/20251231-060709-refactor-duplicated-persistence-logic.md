---
id: "20251231-060709-refactor-duplicated-persistence-logic"
status: todo
title: "Refactor duplicated persistence logic"
created_at: "2025-12-31T06:07:21Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## 📋 Refactor Duplicated Persistence Logic

**Context:**
The `_process_single_window` method in `src/egregora/orchestration/runner.py` contains duplicated logic for persisting documents and handling exceptions. This is done for media, announcements, and profiles.

**Task:**
- Create a helper function to handle the persistence of documents and centralize exception handling.
- This will reduce code duplication and improve the consistency of error handling.

**Code Snippet:**
```python
# src/egregora/orchestration/runner.py

        # TODO: [Taskmaster] Refactor duplicated persistence logic
        if media_mapping and not self.context.enable_enrichment:
            for media_doc in media_mapping.values():
                try:
                    output_sink.persist(media_doc)
                except Exception as e:
                    logger.exception("Failed to write media file: %s", e)
```
