import os
import pytest
import boto3
from moto import mock_aws
from jules.mail import send_message, list_inbox, get_message, mark_read, MAIL_ROOT, BUCKET_NAME

@pytest.fixture(params=["local", "s3"])
def mail_backend(request, tmp_path, monkeypatch):
    """Parametrized fixture to test both local and S3 backends."""
    backend_type = request.param
    monkeypatch.setenv("JULES_MAIL_STORAGE", backend_type)
    
    if backend_type == "local":
        mock_mail_root = tmp_path / "mail"
        monkeypatch.setattr("jules.mail.MAIL_ROOT", mock_mail_root)
        yield "local"
    else:
        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket=BUCKET_NAME)
            yield "s3"

def test_send_and_receive(mail_backend):
    from_id = "curator@team"
    to_id = "refactor@team"
    subject = "Hybrid Test"
    body = "Checking both backends with email-style addressing."
    
    key = send_message(from_id, to_id, subject, body)
    assert key is not None
    
    messages = list_inbox(to_id)
    assert len(messages) == 1
    assert messages[0]["subject"] == subject
    assert messages[0]["from"] == from_id
    assert messages[0]["read"] is False

def test_read_and_mark_seen(mail_backend):
    persona = "reader@team"
    key = send_message("sender@team", persona, "Read Me", "Content")
    
    msg_data = get_message(persona, key)
    assert msg_data["body"] == "Content"
    
    mark_read(persona, key)
    messages = list_inbox(persona)
    assert messages[0]["read"] is True

def test_unread_filter(mail_backend):
    persona = "filter@team"
    k1 = send_message("c@team", persona, "M1", "B1")
    k2 = send_message("c@team", persona, "M2", "B2")
    
    mark_read(persona, k1)
    
    unread = list_inbox(persona, unread_only=True)
    assert len(unread) == 1
    assert unread[0]["key"] == k2
