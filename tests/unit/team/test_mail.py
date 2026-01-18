import os
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

# Add jules to path
sys.path.insert(0, str(Path(__file__).parents[3] / ".team"))

from repo.features.mail import BUCKET_NAME, get_message, list_inbox, mark_read, send_message

pytestmark = pytest.mark.skipif(os.name == "nt", reason="Mail tests with colons fail on Windows")


@pytest.fixture(params=["local", "s3"])
def mail_backend(request, tmp_path, monkeypatch):
    """Parametrized fixture to test both local and S3 backends."""
    backend_type = request.param
    monkeypatch.setenv("JULES_MAIL_STORAGE", backend_type)
    monkeypatch.delenv("AWS_S3_ENDPOINT_URL", raising=False)
    # Patch the module-level variable since it was already imported
    monkeypatch.setattr("repo.features.mail.S3_ENDPOINT", None)

    if backend_type == "local":
        # Run in a temp directory so .team/personas/... is isolated
        monkeypatch.chdir(tmp_path)
        yield "local"
    else:
        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket=BUCKET_NAME)
            yield "s3"


@pytest.mark.usefixtures("mail_backend")
def test_send_and_receive():
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


@pytest.mark.usefixtures("mail_backend")
def test_read_and_mark_seen():
    persona = "reader@team"
    key = send_message("sender@team", persona, "Read Me", "Content")

    msg_data = get_message(persona, key)
    assert msg_data["body"] == "Content"

    mark_read(persona, key)
    messages = list_inbox(persona)
    assert messages[0]["read"] is True


@pytest.mark.skipif(os.name == "nt", reason="Mail tests with colons fail on Windows")
@pytest.mark.usefixtures("mail_backend")
def test_unread_filter():
    persona = "filter@team"
    k1 = send_message("c@team", persona, "M1", "B1")
    k2 = send_message("c@team", persona, "M2", "B2")

    mark_read(persona, k1)

    unread = list_inbox(persona, unread_only=True)
    assert len(unread) == 1
    assert unread[0]["key"] == k2
