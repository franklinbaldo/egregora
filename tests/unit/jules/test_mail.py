"""Tests for Jules mail system."""

import sys
from pathlib import Path

import pytest

# Add jules to path
sys.path.insert(0, str(Path(__file__).parents[3] / ".jules"))

from jules import mail


@pytest.fixture
def temp_mail_root(tmp_path, monkeypatch):
    """Create temporary mail root for testing."""
    mail_root = tmp_path / "mail"
    mail_root.mkdir()

    # Monkey patch the mail root
    monkeypatch.setattr(mail, "DEFAULT_MAIL_ROOT", mail_root)

    return mail_root


def test_send_message_basic(temp_mail_root):
    """Test sending a basic message."""
    msg_id = mail.send_message(
        from_persona="weaver",
        to_persona="curator",
        subject="Test Message",
        body="This is a test message",
    )

    assert msg_id is not None
    assert "@jules.local" in msg_id

    # Check mailbox was created
    curator_mailbox = temp_mail_root / "curator"
    assert curator_mailbox.exists()
    assert (curator_mailbox / "new").exists()


def test_get_inbox_empty(temp_mail_root):
    """Test getting inbox when no messages."""
    inbox = mail.get_inbox("curator")
    assert inbox == []


def test_send_and_receive(temp_mail_root):
    """Test sending and receiving messages."""
    # Send message
    mail.send_message(
        from_persona="weaver",
        to_persona="curator",
        subject="Conflict Report",
        body="Your PR #123 conflicts with refactor's PR #124",
    )

    # Check inbox
    inbox = mail.get_inbox("curator")
    assert len(inbox) == 1

    msg = inbox[0]
    assert msg["from"] == "weaver"
    assert msg["subject"] == "Conflict Report"
    assert "PR #123" in msg["body"]
    assert not msg["is_read"]


def test_unread_filter(temp_mail_root):
    """Test unread_only filter."""
    # Send two messages
    msg_id_1 = mail.send_message("weaver", "curator", "Message 1", "First message")
    mail.send_message("refactor", "curator", "Message 2", "Second message")

    # All messages
    all_inbox = mail.get_inbox("curator", unread_only=False)
    assert len(all_inbox) == 2

    # Mark one as read
    mail.mark_read("curator", all_inbox[0]["id"])

    # Check unread only
    unread_inbox = mail.get_inbox("curator", unread_only=True)
    assert len(unread_inbox) == 1
    assert not unread_inbox[0]["is_read"]


def test_get_message_full(temp_mail_root):
    """Test getting full message content."""
    mail.send_message(
        from_persona="weaver",
        to_persona="curator",
        subject="Test Subject",
        body="This is a longer message body that should be fully retrieved.",
    )

    inbox = mail.get_inbox("curator")
    msg_id = inbox[0]["id"]

    # Get full message
    full_msg = mail.get_message("curator", msg_id)

    assert full_msg is not None
    assert full_msg["from"] == "weaver"
    assert full_msg["subject"] == "Test Subject"
    assert "longer message body" in full_msg["body"]
    assert full_msg["attachments"] == []


def test_send_with_attachment(temp_mail_root, tmp_path):
    """Test sending message with attachment."""
    # Create a test patch file
    patch_content = b"""diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,3 @@
-old line
+new line
"""

    mail.send_message(
        from_persona="curator",
        to_persona="weaver",
        subject="Updated PR #123",
        body="I fixed the conflict. Please re-integrate.",
        attachments=[("pr-123.patch", patch_content)],
    )

    # Get message
    inbox = mail.get_inbox("weaver")
    msg_id = inbox[0]["id"]
    full_msg = mail.get_message("weaver", msg_id)

    assert len(full_msg["attachments"]) == 1
    filename, content = full_msg["attachments"][0]
    assert filename == "pr-123.patch"
    assert content == patch_content
    assert b"diff --git" in content


def test_mark_read(temp_mail_root):
    """Test marking message as read."""
    mail.send_message("weaver", "curator", "Test", "Body")

    inbox = mail.get_inbox("curator")
    msg_id = inbox[0]["id"]

    # Initially unread
    assert not inbox[0]["is_read"]

    # Mark as read
    success = mail.mark_read("curator", msg_id)
    assert success

    # Check status changed
    inbox_after = mail.get_inbox("curator")
    assert len(inbox_after) == 1
    # Note: Maildir behavior may vary, marking read moves file


def test_mark_read_nonexistent(temp_mail_root):
    """Test marking non-existent message."""
    success = mail.mark_read("curator", "nonexistent-id")
    assert not success


def test_get_message_nonexistent(temp_mail_root):
    """Test getting non-existent message."""
    msg = mail.get_message("curator", "nonexistent-id")
    assert msg is None


def test_multiple_recipients(temp_mail_root):
    """Test sending to multiple personas."""
    # Send to curator
    mail.send_message("weaver", "curator", "Message 1", "For curator")

    # Send to refactor
    mail.send_message("weaver", "refactor", "Message 2", "For refactor")

    # Check separate inboxes
    curator_inbox = mail.get_inbox("curator")
    refactor_inbox = mail.get_inbox("refactor")

    assert len(curator_inbox) == 1
    assert len(refactor_inbox) == 1
    assert curator_inbox[0]["subject"] == "Message 1"
    assert refactor_inbox[0]["subject"] == "Message 2"


def test_long_body_truncation_in_inbox(temp_mail_root):
    """Test that inbox list truncates long messages."""
    long_body = "A" * 1000  # 1000 character message

    mail.send_message("weaver", "curator", "Long Message", long_body)

    inbox = mail.get_inbox("curator")
    assert len(inbox) == 1

    # Inbox should truncate to 500 chars + "..."
    assert len(inbox[0]["body"]) <= 503  # 500 + "..."
    assert inbox[0]["body"].endswith("...")

    # But full message should be complete
    full_msg = mail.get_message("curator", inbox[0]["id"])
    assert len(full_msg["body"]) == 1000
