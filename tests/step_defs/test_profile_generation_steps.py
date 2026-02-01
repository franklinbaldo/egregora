from pytest_bdd import scenarios, given, when, then, parsers
import pytest
from unittest.mock import Mock, patch, MagicMock
from ibis import memtable
import asyncio

from egregora.constants import EGREGORA_NAME, EGREGORA_UUID
from egregora.data_primitives.document import DocumentType, Document
from egregora.agents.profile.generator import generate_profile_posts, _generate_profile_content, _build_profile_prompt, ProfileUpdateDecision

# Load scenarios
scenarios("../features/profile_generation.feature")

def parse_datatable(datatable):
    if not datatable:
        return []
    headers = datatable[0]
    rows = datatable[1:]
    return [dict(zip(headers, row)) for row in rows]

# Wrapper for async steps
def async_run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@pytest.fixture
def context():
    return {}

@given(parsers.parse('a profile document is created with subject "{subject}"'))
def create_profile_document(context, subject):
    context['document'] = Document(
        content="# Content",
        type=DocumentType.PROFILE,
        metadata={
            "title": "Title",
            "slug": "slug",
            "authors": [{"uuid": EGREGORA_UUID, "name": EGREGORA_NAME}],
            "subject": subject,
            "date": "2025-03-07",
        },
    )

@then("the document author should be Egregora")
def check_author(context):
    doc = context['document']
    assert doc.metadata["authors"][0]["uuid"] == EGREGORA_UUID
    assert doc.metadata["authors"][0]["name"] == EGREGORA_NAME

@then(parsers.parse('the metadata should contain the subject "{subject}"'))
def check_subject(context, subject):
    doc = context['document']
    assert "subject" in doc.metadata
    assert doc.metadata["subject"] == subject

@given(parsers.parse('a chat context with configured writer model "{model}"'))
def chat_context(context, model):
    ctx = Mock()
    ctx.config = Mock()
    ctx.config.models = Mock()
    ctx.config.models.writer = model

    ctx.output_sink = Mock()
    ctx.output_sink.get_author_profile.return_value = {"bio": "Test Bio", "interests": []}
    ctx.output_format = ctx.output_sink

    ctx.output_dir = "/tmp/test_output"

    # Mock storage read_table
    ctx.state = Mock()
    ctx.state.storage = Mock()

    context['ctx'] = ctx

@given("a chat history with messages:")
def chat_history_table(context, datatable):
    data = parse_datatable(datatable)
    messages = []
    for row in data:
        messages.append({
            "author_uuid": row['author_uuid'],
            "author_name": row['author_name'],
            "text": row['text']
        })
    context['messages'] = messages

@when(parsers.parse('profile posts are generated for the window "{window_date}"'))
def generate_profiles(context, window_date):
    ctx = context['ctx']
    messages = context['messages']

    async def run():
        with patch("egregora.agents.profile.generator._generate_profile_content") as mock_gen:
            mock_gen.return_value = "# Profile content"
            return await generate_profile_posts(ctx=ctx, messages=messages, window_date=window_date)

    context['generated_profiles'] = async_run(run())

@then(parsers.parse('"{count:d}" profile posts should be created'))
def check_profile_count(context, count):
    profiles = context['generated_profiles']
    assert len(profiles) == count

@then(parsers.parse('all generated documents should be of type "{doc_type}"'))
def check_doc_type(context, doc_type):
    profiles = context['generated_profiles']
    # Map string type to enum
    dt = getattr(DocumentType, doc_type)
    assert all(p.type == dt for p in profiles)

@then("all generated documents should be authored by Egregora")
def check_all_authors(context):
    profiles = context['generated_profiles']
    assert all(p.metadata["authors"][0]["uuid"] == EGREGORA_UUID for p in profiles)

@given(parsers.parse('a chat history with "{count:d}" messages from "{author}"'))
def chat_history_count(context, count, author):
    messages = [
        {"author_uuid": f"{author}-uuid", "author_name": author, "text": f"Message {i}"}
        for i in range(count)
    ]
    context['messages'] = messages
    context['target_author'] = author

@when(parsers.parse('profile generation is triggered for "{author}"'))
def trigger_profile_generation(context, author):
    ctx = context['ctx']
    messages = context['messages']
    window_date = "2025-03-07"

    context['call_args'] = []

    async def capture_call(ctx, author_messages, **kwargs):
        context['call_args'].append(len(author_messages))
        return "# Profile"

    async def run():
        with patch("egregora.agents.profile.generator._generate_profile_content", side_effect=capture_call):
            await generate_profile_posts(ctx, messages, window_date)

    async_run(run())

@then(parsers.parse('the content generator should receive "{count:d}" messages'))
def check_generator_messages(context, count):
    call_args = context['call_args']
    assert call_args[0] == count

@given(parsers.parse('an existing profile for "{author}" with bio "{bio}"'))
def existing_profile(context, author, bio):
    ctx = context['ctx']
    ctx.output_sink.get_author_profile.return_value = {"bio": bio, "interests": ["Old Interest"]}

    # Mock DB for load_author_profile_content
    mock_profiles_table = MagicMock()
    mock_profile_df = memtable(
        {"content": [f"---\nsubject_uuid: {author}-uuid\n---\n{bio}"], "subject_uuid": [f"{author}-uuid"]}
    )
    mock_profiles_table.filter.return_value.execute.return_value = mock_profile_df.execute()

    # Store in context to setup side_effect later if needed
    context['mock_profiles_table'] = mock_profiles_table

@given(parsers.parse('new messages from "{author}" about "{topic}"'))
def new_messages_topic(context, author, topic):
    messages = [
        {"text": f"I'm interested in {topic}", "timestamp": "2025-03-01"},
        {"text": "More info", "timestamp": "2025-03-02"},
        {"text": "Even more", "timestamp": "2025-03-03"},
    ]
    context['author_messages'] = messages
    context['author_name'] = author
    context['author_uuid'] = f"{author}-uuid"
    context['topic'] = topic

@when("the LLM decides the profile content")
def llm_decides(context):
    ctx = context['ctx']
    author_messages = context['author_messages']
    author_name = context['author_name']
    author_uuid = context['author_uuid']

    # Setup DB mocks
    mock_posts_table = MagicMock()
    mock_posts_df = memtable(
        {
            "slug": [],
            "title": [],
            "content": [],
            "date": [],
            "summary": [],
        }
    )
    mock_posts_table.filter.return_value.execute.return_value = mock_posts_df.execute()

    mock_profiles_table = context.get('mock_profiles_table', MagicMock())

    def read_table_side_effect(table_name):
        if table_name == "posts":
            return mock_posts_table
        if table_name == "profiles":
            return mock_profiles_table
        return MagicMock()

    ctx.state.storage.read_table.side_effect = read_table_side_effect

    async def run():
        with patch("egregora.agents.profile.generator._call_llm_decision") as mock_llm:
            mock_llm.return_value = ProfileUpdateDecision(
                significant=True,
                content=f"# {author_name}'s {context.get('topic', 'Focus')}\n\nContent...",
            )

            content = await _generate_profile_content(
                ctx=ctx, author_messages=author_messages, author_name=author_name, author_uuid=author_uuid
            )

            context['mock_llm'] = mock_llm
            context['generated_content'] = content

    async_run(run())

@then(parsers.parse('the prompt should contain "{text}"'))
def check_prompt_text(context, text):
    if 'mock_llm' in context:
        mock_llm = context['mock_llm']
        call_args = mock_llm.call_args[0]
        prompt = call_args[0]
    else:
        prompt = context.get('prompt', '')
    assert text in prompt

@then("the generated content should reflect the LLM decision")
def check_content_decision(context):
    content = context['generated_content']
    topic = context.get('topic', 'Focus')
    assert topic in content or "Content..." in content

@given(parsers.parse('messages from "{author}":'))
def messages_from_author_table(context, author, datatable):
    data = parse_datatable(datatable)
    messages = []
    for row in data:
        messages.append({"text": row['text'], "timestamp": row['timestamp']})
    context['author_messages'] = messages
    context['author_name'] = author
    context['window_date'] = "2025-03-07"
    context['existing_profile'] = None

@when(parsers.parse('the profile generation prompt is built for "{author}"'))
def build_prompt(context, author):
    messages = context['author_messages']
    window_date = context['window_date']
    existing_profile = context.get('existing_profile')

    prompt = _build_profile_prompt(
        author_name=author,
        author_messages=messages,
        window_date=window_date,
        existing_profile=existing_profile
    )
    context['prompt'] = prompt

@then("the prompt should contain all message texts")
def check_prompt_all_messages(context):
    prompt = context['prompt']
    messages = context['author_messages']
    for msg in messages:
        assert msg['text'] in prompt

@then("the prompt should ask for analysis")
def check_prompt_analysis(context):
    prompt = context['prompt']
    assert "analyze" in prompt.lower() or "analysis" in prompt.lower()
    assert (
        "positive" in prompt.lower() or "flattering" in prompt.lower() or "appreciative" in prompt.lower()
    )

@then(parsers.parse('the prompt should specify "{format_type}" post format'))
def check_prompt_format(context, format_type):
    prompt = context['prompt']
    assert format_type.lower() in prompt.lower()
    assert "paragraph" in prompt.lower()

@given(parsers.parse('an existing profile for "{author}" with interests "{interests_str}"'))
def existing_profile_interests(context, author, interests_str):
    interests = interests_str
    if interests_str == "None":
        interests = None

    # Existing profile context setup
    context['existing_profile'] = {"bio": "Bio here", "interests": interests}
    context['author_name'] = author
    context['window_date'] = "2025-03-07"
