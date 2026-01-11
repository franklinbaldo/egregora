# Jules Mail System 📬

Async messaging system for persona coordination using standard Maildir format.

## Quick Start

### Send a Message

```bash
python jules/mail_cli.py send \
  --to curator \
  --from weaver \
  --subject "Conflict in PR #123" \
  --body "Your PR conflicts with refactor's changes. Please rebase."
```

### Check Inbox

```bash
python jules/mail_cli.py inbox --persona curator
python jules/mail_cli.py inbox --persona curator --unread  # Only new messages
```

### Read a Message

```bash
python jules/mail_cli.py read <message-id> --persona curator
```

## Directory Structure

```
.jules/mail/
├── curator/
│   ├── new/      # Unread messages
│   ├── cur/      # Read messages
│   └── tmp/      # Temporary (internal)
├── weaver/
│   ├── new/
│   ├── cur/
│   └── tmp/
└── ...
```

## Use Cases

### 1. Conflict Notification

```bash
# Weaver notifies curator of conflicts
python jules/mail_cli.py send \
  --to curator \
  --from weaver \
  --subject "Conflict in PR #123" \
  --body "Your PR conflicts with PR #124 (refactor). Please rebase and resubmit."
```

### 2. Patch Attachment

```bash
# Send updated patch file
python jules/mail_cli.py send \
  --to weaver \
  --from curator \
  --subject "Re: Conflict in PR #123" \
  --body "Fixed conflict. Please re-integrate." \
  --attach /tmp/pr-123.patch
```

### 3. Coordination

```bash
# Request feedback
python jules/mail_cli.py send \
  --to refactor \
  --from curator \
  --subject "Review needed" \
  --body "Can you review the API changes in PR #125?"
```

## Architecture

- **Format**: RFC 822 (standard email) in Maildir structure (RFC 3501)
- **Storage**: Filesystem-based, one file per message
- **Thread-safe**: Append-only writes, no locks needed
- **Git-friendly**: Plain text files, easy to track changes
- **Attachments**: Full MIME support for .patch files

## Integration with Scheduler

Personas check their mailbox at start:

```python
# In persona prompt
inbox = get_inbox("curator", unread_only=True)
if inbox:
    for msg in inbox:
        print(f"Message from {msg['from']}: {msg['subject']}")
        # Handle conflict, rebase, etc.
```

Scheduler checks all mailboxes after each tick:

```python
# In scheduler
for persona_id in all_personas:
    inbox = get_inbox(persona_id, unread_only=True)
    if inbox:
        # Re-run persona to handle messages
        create_persona_session(persona_id, ...)
```

## Testing

```bash
# Run tests
pytest tests/unit/jules/test_mail.py -v

# 11/11 tests passing
```

## Implementation

See:
- `jules/mail.py` - Backend API
- `jules/mail_cli.py` - CLI tool
- `tests/unit/jules/test_mail.py` - Test suite
- `PARALLEL_PERSONAS_PLAN.md` - Full architecture docs
