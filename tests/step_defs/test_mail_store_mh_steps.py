import pytest
from jules.features.mail import LocalMhBackend
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/mail_store_mh.feature")


@pytest.fixture
def mh_backend(tmp_path):
    # Use a temp path for the mailbox to ensure isolation
    mail_path = tmp_path / "mail"
    return LocalMhBackend(root_path=mail_path)


@pytest.fixture
def context():
    return {}


@given("an empty MH mailbox")
def empty_mailbox(mh_backend):
    pass


@given(parsers.parse('a persona "{persona}"'))
def set_persona(context, persona):
    context["persona"] = persona


@when(parsers.parse('I add a message from "{sender}" with subject "{subject}"'))
def add_message(mh_backend, context, sender, subject):
    persona = context.get("persona", "user")
    mid = mh_backend.send_message(sender, persona, subject, "Body content")
    context["last_msg_id"] = mid
    context["last_msg_body"] = "Body content"


@then(parsers.parse('the message should be in "{sequence}"'))
def check_sequence(mh_backend, context, sequence):
    persona = context.get("persona", "user")
    mid = context["last_msg_id"]
    seq_name = mh_backend._get_seq_name(persona, sequence)
    seqs = mh_backend.mb.get_sequences()
    # mid is string, sequences hold ints
    assert int(mid) in seqs.get(seq_name, []), f"Message {mid} not found in sequence {seq_name}"


@then(parsers.parse('the message should not be in "{sequence}"'))
def check_not_sequence(mh_backend, context, sequence):
    persona = context.get("persona", "user")
    mid = context["last_msg_id"]
    seq_name = mh_backend._get_seq_name(persona, sequence)
    seqs = mh_backend.mb.get_sequences()
    assert int(mid) not in seqs.get(seq_name, []), (
        f"Message {mid} found in sequence {seq_name} but should not be"
    )


@then(parsers.parse('the message content should match "{text}"'))
def check_content(mh_backend, context, text):
    persona = context.get("persona", "user")
    mid = context["last_msg_id"]
    msg = mh_backend.get_message(persona, mid)
    assert msg["subject"] == text


@given(parsers.parse('a message exists in "{sequence}"'))
def ensure_message_in_sequence(mh_backend, context, sequence):
    persona = context.get("persona", "user")
    # specific steps to put message in sequence
    mid = mh_backend.send_message("sender", persona, "Subject", "Body")
    context["last_msg_id"] = mid

    # Default is inbox + unread
    # If sequence is inbox or unread, we are good.
    if sequence in {"inbox", "unread"}:
        pass
    elif sequence == "archived":
        mh_backend.archive(persona, mid)
    elif sequence == "trash":
        mh_backend.trash(persona, mid)

    # Verify it is there
    seq_name = mh_backend._get_seq_name(persona, sequence)
    assert int(mid) in mh_backend.mb.get_sequences().get(seq_name, [])


@given("a message exists")
def create_msg(mh_backend, context):
    ensure_message_in_sequence(mh_backend, context, "inbox")


@when("I mark the message as read")
def mark_read(mh_backend, context):
    persona = context.get("persona", "user")
    mid = context["last_msg_id"]
    mh_backend.mark_read(persona, mid)


@when("I mark the message as unread")
def mark_unread(mh_backend, context):
    persona = context.get("persona", "user")
    mid = context["last_msg_id"]
    mh_backend.mark_unread(persona, mid)


@when("I archive the message")
def archive(mh_backend, context):
    persona = context.get("persona", "user")
    mid = context["last_msg_id"]
    mh_backend.archive(persona, mid)


@when("I unarchive the message")
def unarchive(mh_backend, context):
    persona = context.get("persona", "user")
    mid = context["last_msg_id"]
    mh_backend.unarchive(persona, mid)


@when("I trash the message")
def trash(mh_backend, context):
    persona = context.get("persona", "user")
    mid = context["last_msg_id"]
    mh_backend.trash(persona, mid)


@when("I restore the message")
def restore(mh_backend, context):
    persona = context.get("persona", "user")
    mid = context["last_msg_id"]
    mh_backend.restore(persona, mid)


@when(parsers.parse('I add the tag "{tag}"'))
def add_tag(mh_backend, context, tag):
    persona = context.get("persona", "user")
    mid = context["last_msg_id"]
    mh_backend.tag_add(persona, mid, tag)


@then(parsers.parse('the tags list should include "{tag}"'))
def check_tag_exists(mh_backend, context, tag):
    persona = context.get("persona", "user")
    mid = context["last_msg_id"]
    tags = mh_backend.list_tags(persona, mid)
    assert tag in tags


@when(parsers.parse('I remove the tag "{tag}"'))
def remove_tag(mh_backend, context, tag):
    persona = context.get("persona", "user")
    mid = context["last_msg_id"]
    mh_backend.tag_remove(persona, mid, tag)


@then(parsers.parse('the tags list should not include "{tag}"'))
def check_tag_not_exists(mh_backend, context, tag):
    persona = context.get("persona", "user")
    mid = context["last_msg_id"]
    tags = mh_backend.list_tags(persona, mid)
    assert tag not in tags


@then('no file in the mailbox directory should have ":" in its name')
def check_files(mh_backend):
    # Check recursively in mailbox root
    # MH creates numeric files like '1', '2'.
    # If it uses Maildir-style names with colons (like 12345:2,S), that's bad for Windows.
    # MH standard is strictly numeric names.
    root = mh_backend.root_path
    for p in root.rglob("*"):
        assert ":" not in p.name
