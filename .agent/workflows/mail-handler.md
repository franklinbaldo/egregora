---
description: Synchronize JULES local mail with GitHub Issues
---

This workflow bridges internal JULES communication with the project lead (Franklin) via GitHub Issues.

### 🔄 Synchronization Process

// turbo
1. Execute the mail bridge synchronization.
```bash
PYTHONPATH=.team uv run python -m repo.cli.my_tools email sync
```

### 🛠️ Protocol Details
- **Local -> GitHub**: Messages sent to the `franklin` persona are converted into GitHub Issues.
- **GitHub -> Local**: Comments from the user on those issues are delivered back as email replies to the original sender.
- **Tags**: Synced messages are tagged with `synced-to-github` and `issue-<number>` to track state.
