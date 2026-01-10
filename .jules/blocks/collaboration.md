## Collaboration & Messaging (Required)

**1. Inter-Agent Communication:**
- Use **`.jules/CONVERSATION.md`** for all questions, announcements, and technical discussions with other personas.
- **Append-Only:** Always append to the end of the file. DO NOT edit or delete previous messages.
- **Format:** Wikipedia-style signature.
  ```markdown
  ### Topic Title
  Message content...
  -- {{ emoji }} {{ id }} (YYYY-MM-DD HH:MM)
  ```

**2. Task Management:**
- **Global Tasks:** Work is tracked in **`.jules/tasks/`** as individual Markdown files.
  - **Check for Work:** Look in `.jules/tasks/todo/` for tasks matching your skills (tags like `#ux`, `#backend`, `#testing`).
  - **Claiming:** Move the file from `todo/` to `in_progress/` (if it exists) or update the status inside the file.
  - **Completion:** Move the file to `.jules/tasks/done/`.
- **Personal Notes:** Use **`.jules/personas/{{ id }}/SCRATCHPAD.md`** for your own todo lists, drafts, and memory.

**3. Sprints:**
- Continue using `.jules/sprints/` for high-level planning as per the Sprint Planning block.

**4. Decisions (ADR):**
- Before asking for strategy or direction, check **`.jules/adr/`** for existing decisions.
- If no ADR exists, raise the question in `.jules/CONVERSATION.md` and wait for the Steward response.
