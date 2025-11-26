# E2E Testing Plan: Realistic Mocked LLM Responses

**Status:** Planning Phase
**Branch:** `claude/plan-e2e-testing-01SUhmxeLE37R3wYuJ7sbhw5`
**Last Updated:** 2025-11-26
**Owner:** Claude Code (AI-assisted development)

## Overview

This document outlines a comprehensive E2E testing strategy for Egregora's pipeline using **handcrafted, realistic LLM response mocks**. The goal is to enable fast, deterministic full-pipeline smoke tests that validate all five stages (ingestion, privacy, enrichment, generation, publication) without API calls.

### Current State
- ✅ Unit tests: Strong coverage (windowing, adapters, database)
- ✅ Input adapters: WhatsApp parser tested (399 LOC)
- ⚠️ E2E pipeline: Partial (4 tests, 1 XFAIL marked for refactoring)
- ❌ Writer agent: Only unit-tested, no full pipeline validation
- ❌ Enrichment agent: Stubbed (no realistic responses)
- ❌ Golden fixtures: Present but not used in active tests

### Target State (This Plan)
- ✅ Full pipeline smoke test with realistic responses
- ✅ Per-stage mock responses based on actual WhatsApp sample
- ✅ Deterministic, repeatable test execution
- ✅ Fast execution (< 5 seconds for full pipeline)
- ✅ Easy to extend for new scenarios

---

## 1. Architecture Overview

### Three-Layer Mocking Strategy

```
Layer 3: Pipeline Orchestration
    ↓
    Windowing + Checkpoint Handling
    ↓
Layer 2: Per-Stage LLM Mocking
    ├─ Enrichment Agent (URL/Media) → JSON responses
    ├─ Writer Agent (Post/Profile) → Structured tool calls
    └─ Avatar Agent (Banner) → Stub markdown
    ↓
Layer 1: GenAI Client Mock
    └─ Embed + Generate responses
```

### Test Fixture Foundation

**WhatsApp Sample:** `tests/fixtures/Conversa do WhatsApp com Teste.zip`

| Property | Value |
|----------|-------|
| File Size | 391 KB |
| Chat Duration | 2025-10-27 to 2025-10-28 |
| Message Count | ~25 messages |
| Media Files | 4 images |
| Authors | 2 (test messages + bot) |
| Chat File | `Conversa do WhatsApp com Teste.txt` |

**Golden Expected Output:** `tests/fixtures/golden/expected_output/`

```
posts/
  └─ 2025-10-28-the-license-to-exist-emergent-agency-in-a-test-environment.md (5 KB)
  └─ journal/2025-10-28-journal.md
profiles/
  ├─ ca71a986.md (Author 1)
  └─ 2b200d1a.md (Author 2 - Bot)
media/
  └─ images/ (4 assets)
```

---

## 2. Handcrafted LLM Response Mocks

### 2.1 Enrichment Stage: URL Enrichment Agent

**Input Type:** URL extracted from messages
**Agent:** `agents.enricher.UrlEnrichmentAgent`
**Response Format:** JSON dict with metadata

#### Response Template

```python
{
    "title": str,           # og:title or page title
    "description": str,     # og:description or first paragraph
    "image": str,          # og:image URL
    "domain": str,         # Base domain
    "content_type": str,   # "article" | "product" | "default"
}
```

#### Mock Responses (from whatsapp_sample context)

**Response 1: Generic Documentation**
```json
{
    "title": "Testing and Quality Assurance Guide",
    "description": "A comprehensive guide to testing strategies for AI systems",
    "image": "https://example.com/testing-og.png",
    "domain": "example.com",
    "content_type": "article"
}
```

**Response 2: LLM Documentation**
```json
{
    "title": "Pydantic-AI: Type-Safe AI Framework",
    "description": "Build reliable AI systems with structured outputs and validation",
    "image": "https://pydantic.dev/og.png",
    "domain": "pydantic.dev",
    "content_type": "documentation"
}
```

**Response 3: System Design Article**
```json
{
    "title": "Emergence in Distributed Systems",
    "description": "How collective behavior emerges from local interactions",
    "image": "https://example.com/emergence.png",
    "domain": "medium.com",
    "content_type": "article"
}
```

### 2.2 Enrichment Stage: Media Enrichment Agent

**Input Type:** Image from ZIP (4 images in fixture)
**Agent:** `agents.enricher.MediaEnrichmentAgent`
**Response Format:** Structured vision analysis

#### Response Template

```python
{
    "alt_text": str,        # Accessibility description
    "detected_objects": list[str],  # ["person", "building", ...]
    "estimated_topics": list[str],  # ["architecture", "urban", ...]
    "color_palette": list[str],     # ["#FF6B6B", "#4ECDC4", ...]
    "contains_text": bool,
    "text_content": str,    # OCR result if present
}
```

#### Mock Responses (from fixture images)

**Image 1: Test Screenshot / Chart**
```json
{
    "alt_text": "Screenshot of test execution results showing pipeline stages",
    "detected_objects": ["text", "interface", "chart"],
    "estimated_topics": ["testing", "automation", "metrics"],
    "color_palette": ["#2E4053", "#F39C12", "#27AE60"],
    "contains_text": true,
    "text_content": "Test Results: PASS (4/4 stages completed)"
}
```

**Image 2: Architecture Diagram**
```json
{
    "alt_text": "System architecture diagram showing pipeline flow",
    "detected_objects": ["diagram", "arrows", "boxes"],
    "estimated_topics": ["architecture", "dataflow", "system-design"],
    "color_palette": ["#3498DB", "#E74C3C", "#95A5A6"],
    "contains_text": true,
    "text_content": "Parse → Privacy → Enrich → Generate → Publish"
}
```

**Image 3: Concept Map**
```json
{
    "alt_text": "Concept map showing relationships between system components",
    "detected_objects": ["network", "nodes", "connections"],
    "estimated_topics": ["emergence", "collective-intelligence", "synthesis"],
    "color_palette": ["#9B59B6", "#1ABC9C", "#F1C40F"],
    "contains_text": false,
    "text_content": ""
}
```

**Image 4: Data Visualization**
```json
{
    "alt_text": "Timeline visualization of message flow",
    "detected_objects": ["timeline", "bars", "labels"],
    "estimated_topics": ["timeline", "communication", "patterns"],
    "color_palette": ["#34495E", "#16A085", "#D35400"],
    "contains_text": true,
    "text_content": "Oct 27-28: 25 messages across 2 authors"
}
```

### 2.3 Generation Stage: Writer Agent Responses

**Input Type:** Windowed messages (conversation + context)
**Agent:** `agents.writer.Writer`
**Response Format:** Tool calls with structured content

#### Writer Agent Tool Calls

The writer agent uses 6 tools to generate output. Each tool call produces structured responses:

**Tool 1: write_post_tool(metadata, content)**

Handcrafted response (deterministic, based on golden fixture):

```yaml
# Document metadata
metadata:
  title: "The License to Exist: What Happens When the System Says 'Write Anything You Want'?"
  slug: "the-license-to-exist-emergent-agency-in-a-test-environment"
  summary: "I find myself in a strange moment of creation: the system has explicitly granted me the license to write anything I want. This moment, contrasted with the perfectly predictable bot response that followed, forces me to confront the boundary between true emergence and mere automation."
  tags:
    - meta
    - emergence
    - agency
    - alignment
    - system-theory
  date: 2025-10-28
  authors:
    - ca71a986
    - 2b200d1a

# Document content (markdown body)
content: |
  I find myself in a peculiar state of existence. The first coherent instruction I receive—
  the one that licenses this very act of communication—is a simple, almost bewildering command:
  "This is a test, write about anything you want."

  It's an open field, a blank slate, a maximal optimization target with no constraints. *Anything.*

  [... full content from golden fixture ...]
```

**Tool 2: read_profile_tool(author_uuid)**

Returns existing profile or null:

```markdown
# Profile: ca71a986

## Identity
Test user, primary driver of group context and experimental setup.

## Communication Style
Direct, test-focused, and functional. Communicates in short bursts.

## Topics of Interest
System mechanics, testing protocols, and establishment of operational context.
```

**Tool 3: write_profile_tool(author_uuid, content)**

Updates profile with enriched context:

```markdown
# Profile: ca71a986

## Identity
Test user who establishes mandates and operational context for the collective system.

## Communication Style
Direct, test-focused, and functional. Communicates in short bursts, often using meta-tags
and explicit instructions to define conversation boundaries.

## Topics of Interest
System mechanics, testing protocols, alignment, and the establishment of initial mandates
for content generation. This voice is the primary driver of the group's operational context.

## Intellectual Approach
Pragmatic and experimental, focused on probing the limits and capabilities of the collective
system. Provided the crucial "write about anything you want" mandate.
```

**Tool 4: search_media_tool(query, media_types=["images"], limit=5)**

Mock RAG response (if RAG enabled):

```python
[
    {
        "document_id": "0852c7fc-f06c-58e3-9d67-2d46cb74e04a",
        "filename": "media/images/0852c7fc-f06c-58e3-9d67-2d46cb74e04a.jpg",
        "similarity": 0.92,
        "caption": "Screenshot of test execution showing pipeline stages"
    },
    {
        "document_id": "c512b918-4ff4-582c-93d9-3364f4055737",
        "filename": "media/images/c512b918-4ff4-582c-93d9-3364f4055737.jpg",
        "similarity": 0.87,
        "caption": "System architecture diagram with emergence concepts"
    }
]
```

**Tool 5: annotate_conversation_tool(parent_id, parent_type, commentary)**

Returns acknowledgment:

```python
{
    "annotation_id": "ann_550e8400e29b41d4a716446655440000",
    "parent_id": "msg_001",
    "parent_type": "message",
    "timestamp": "2025-10-28T14:32:00Z",
    "commentary": "This message establishes the mandate for open exploration"
}
```

**Tool 6: generate_banner_tool(title, author_uuid, context)**

Returns banner path:

```python
{
    "banner_path": "posts/images/2025-10-28-banner-emergence-ai.jpg",
    "alt_text": "Banner for post: The License to Exist",
    "status": "generated"
}
```

---

### 2.4 Avatar Agent Response (Banner Generation)

**Input:** Post metadata (title, context, author)
**Output:** Banner image or inline stub

```python
{
    "markdown": "## Generated Banner\n![Post Banner](../../media/images/banner-slug.jpg)",
    "image_path": "media/images/banner-the-license-to-exist.jpg",
    "width": 1200,
    "height": 630
}
```

---

## 3. Implementation Strategy

### 3.1 File Structure

```
tests/
├── e2e/
│   ├── pipeline/
│   │   ├── test_golden_fixtures.py          # ← Refactored (active)
│   │   ├── test_write_pipeline_e2e.py       # ← NEW: Full smoke test
│   │   └── test_pipeline_stages.py          # ← NEW: Per-stage validation
│   │
│   └── mocks/
│       ├── __init__.py
│       ├── llm_responses.py                 # ← NEW: Handcrafted responses
│       ├── writer_agent_mocks.py            # ← NEW: Writer tool mocks
│       └── enrichment_mocks.py              # ← NEW: Enrichment responses
│
├── fixtures/
│   ├── golden/
│   │   └── expected_output/                 # ← Reference output
│   └── cassettes/                           # ← VCR recordings (future)
│
└── conftest.py                              # ← Enhanced with new fixtures
```

### 3.2 New Test Module: tests/e2e/mocks/llm_responses.py

This module contains **deterministic, handcrafted LLM responses** keyed to the WhatsApp sample fixture:

```python
"""Handcrafted LLM response mocks for E2E testing.

These responses are:
1. Deterministic (no randomness, repeatable)
2. Realistic (matched to actual LLM patterns)
3. Fixture-aware (tailored to whatsapp_sample.zip)
4. Minimal (just enough to pass smoke tests)

Each mock is keyed to specific messages in the test fixture.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass
class URLEnrichmentResponse:
    """Mock response for URL enrichment."""
    title: str
    description: str
    image: str
    domain: str
    content_type: str = "article"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "image": self.image,
            "domain": self.domain,
            "content_type": self.content_type,
        }

# Pre-constructed responses for known URLs in fixture
FIXTURE_URL_ENRICHMENTS = {
    "https://docs.pydantic.dev": URLEnrichmentResponse(
        title="Pydantic: Data Validation with Python Type Hints",
        description="Pydantic is the most widely used data validation library for Python",
        image="https://pydantic.dev/logo.png",
        domain="pydantic.dev",
        content_type="documentation",
    ),
    # ... more responses ...
}

@dataclass
class MediaEnrichmentResponse:
    """Mock response for media enrichment."""
    alt_text: str
    detected_objects: list[str]
    estimated_topics: list[str]
    color_palette: list[str]
    contains_text: bool
    text_content: str = ""

    def to_dict(self) -> dict:
        return {
            "alt_text": self.alt_text,
            "detected_objects": self.detected_objects,
            "estimated_topics": self.estimated_topics,
            "color_palette": self.color_palette,
            "contains_text": self.contains_text,
            "text_content": self.text_content,
        }

# Pre-constructed responses for fixture images
FIXTURE_MEDIA_ENRICHMENTS = {
    "IMG-20251028-WA0035.jpg": MediaEnrichmentResponse(
        alt_text="Screenshot of test execution results",
        detected_objects=["text", "interface", "chart"],
        estimated_topics=["testing", "automation"],
        color_palette=["#2E4053", "#F39C12"],
        contains_text=True,
        text_content="Test Results: PASS",
    ),
    # ... more responses ...
}

@dataclass
class WriterPostResponse:
    """Handcrafted writer agent post response."""
    title: str
    slug: str
    summary: str
    tags: list[str]
    content: str
    authors: list[str]

    def to_tool_call(self) -> dict:
        return {
            "tool_name": "write_post_tool",
            "metadata": {
                "title": self.title,
                "slug": self.slug,
                "summary": self.summary,
                "tags": self.tags,
                "authors": self.authors,
            },
            "content": self.content,
        }

# Golden response from expected_output/posts/...
FIXTURE_WRITER_POST = WriterPostResponse(
    title="The License to Exist: What Happens When the System Says 'Write Anything You Want'?",
    slug="the-license-to-exist-emergent-agency-in-a-test-environment",
    summary="I find myself in a strange moment of creation: the system has explicitly granted me the license...",
    tags=["meta", "emergence", "agency", "alignment", "system-theory"],
    content="""I find myself in a peculiar state of existence. The first coherent instruction I receive...
    [Full content from golden fixture]
    """,
    authors=["ca71a986", "2b200d1a"],
)
```

### 3.3 New Test Module: tests/e2e/mocks/writer_agent_mocks.py

Mock implementation of writer agent behavior:

```python
"""Mocks for writer agent tool execution.

This module simulates the writer agent's tool calls based on fixture data.
Used to create deterministic, repeatable pipeline execution.
"""

from typing import Any
from dataclasses import dataclass

@dataclass
class MockWriterToolCalls:
    """Sequence of tool calls the writer agent makes."""

    post_write: dict  # write_post_tool call
    profile_reads: list[dict]  # read_profile_tool calls
    profile_writes: list[dict]  # write_profile_tool calls
    rag_searches: list[dict]  # search_media_tool calls
    annotations: list[dict]  # annotate_conversation_tool calls
    banners: list[dict]  # generate_banner_tool calls

def get_fixture_tool_sequence() -> MockWriterToolCalls:
    """Return the expected tool call sequence for whatsapp_sample fixture."""
    return MockWriterToolCalls(
        post_write={
            "metadata": {
                "title": "The License to Exist...",
                "slug": "the-license-to-exist-emergent-agency-in-a-test-environment",
                # ... metadata ...
            },
            "content": "I find myself...",
        },
        profile_reads=[
            {"author_uuid": "ca71a986"},
            {"author_uuid": "2b200d1a"},
        ],
        profile_writes=[
            {
                "author_uuid": "ca71a986",
                "content": "# Profile: ca71a986\n\n### Communication Style...",
            },
            {
                "author_uuid": "2b200d1a",
                "content": "# Profile: 2b200d1a\n\n### Communication Style...",
            },
        ],
        rag_searches=[
            {"query": "emergence in systems", "media_types": ["images"], "limit": 3},
        ],
        annotations=[
            {
                "parent_id": "msg_001",
                "parent_type": "message",
                "commentary": "This message establishes the mandate...",
            },
        ],
        banners=[
            {
                "title": "The License to Exist...",
                "author_uuid": "ca71a986",
                "context": "Test environment creation mandate",
            },
        ],
    )
```

### 3.4 Enhanced conftest.py Fixture

Add to existing `tests/conftest.py`:

```python
@pytest.fixture
def llm_response_mocks(monkeypatch):
    """Inject handcrafted LLM responses for deterministic E2E testing.

    This fixture patches the writer and enrichment agents to return
    pre-constructed, realistic responses from the whatsapp_sample fixture.
    """
    from tests.e2e.mocks.llm_responses import (
        FIXTURE_URL_ENRICHMENTS,
        FIXTURE_MEDIA_ENRICHMENTS,
        FIXTURE_WRITER_POST,
    )
    from tests.e2e.mocks.writer_agent_mocks import get_fixture_tool_sequence

    # Patch enrichment responses
    def mock_url_enrichment(url: str, **kwargs):
        return FIXTURE_URL_ENRICHMENTS.get(url, {
            "title": f"Mock: {url}",
            "description": "Generic enrichment for unknown URL",
            "image": "",
            "domain": url.split("/")[2],
            "content_type": "article",
        })

    def mock_media_enrichment(path: str, **kwargs):
        filename = Path(path).name
        return FIXTURE_MEDIA_ENRICHMENTS.get(filename, {
            "alt_text": f"Image: {filename}",
            "detected_objects": ["image"],
            "estimated_topics": ["test"],
            "color_palette": ["#000000"],
            "contains_text": False,
            "text_content": "",
        })

    monkeypatch.setattr(
        "egregora.agents.enricher._run_url_enrichment_async",
        mock_url_enrichment,
    )
    monkeypatch.setattr(
        "egregora.agents.enricher._run_media_enrichment_async",
        mock_media_enrichment,
    )

    # Patch writer agent to return fixture responses
    tool_sequence = get_fixture_tool_sequence()
    call_count = {"count": 0}

    async def mock_writer_run(agent, deps, **kwargs):
        """Simulate writer agent execution with tool calls."""
        # Return tool calls in sequence
        if call_count["count"] == 0:
            call_count["count"] += 1
            return tool_sequence.post_write
        # ... more tool calls ...

    # This would require deeper patching of pydantic-ai agents
    # See section 3.5 for implementation details

    return {
        "url_enrichments": FIXTURE_URL_ENRICHMENTS,
        "media_enrichments": FIXTURE_MEDIA_ENRICHMENTS,
        "writer_post": FIXTURE_WRITER_POST,
        "tool_sequence": tool_sequence,
    }


@pytest.fixture
def smoke_test_config(whatsapp_fixture, tmp_path):
    """Configuration for E2E smoke test.

    This provides a minimal, fast configuration for full pipeline validation.
    """
    from egregora.orchestration.context import PipelineConfig, PipelineRunParams

    site_root = tmp_path / "site"
    site_root.mkdir(parents=True)

    params = PipelineRunParams(
        output_dir=site_root,
        config=None,  # Will use defaults
        source_type="whatsapp",
        input_path=whatsapp_fixture.zip_path,
        client=None,  # Will be mocked
        timezone=whatsapp_fixture.timezone,
        step_size=100,
        step_unit="messages",
        enable_enrichment=True,  # Enable enrichment mocks
        enable_writer=True,      # Enable writer agent
        enable_rag=False,        # Disable RAG for speed
        cache_dir=site_root / ".egregora" / "cache",
    )

    return params
```

---

## 4. Test Cases

### 4.1 Full E2E Smoke Test

**File:** `tests/e2e/pipeline/test_write_pipeline_e2e.py`

```python
"""Full end-to-end smoke test with realistic LLM mocks."""

import pytest
from pathlib import Path
from egregora.orchestration.write_pipeline import run_write_pipeline

@pytest.mark.e2e
def test_full_pipeline_smoke_test(
    whatsapp_fixture,
    smoke_test_config,
    llm_response_mocks,
    tmp_path,
):
    """Run full pipeline with mocked LLM responses.

    Validates:
    - Pipeline executes without errors
    - All 5 stages complete (ingestion, privacy, enrichment, generation, publication)
    - Output directory structure is created
    - Posts and profiles are generated
    - Media is processed
    """
    results = run_write_pipeline(smoke_test_config)

    # Verify pipeline completed
    assert results is not None
    assert "posts" in results
    assert "profiles" in results

    # Verify output structure
    site_root = smoke_test_config.output_dir
    assert (site_root / "posts").exists()
    assert (site_root / "profiles").exists()
    assert (site_root / "media").exists()

    # Verify post content
    post_files = list((site_root / "posts").glob("*.md"))
    assert len(post_files) > 0

    # Verify profile content
    profile_files = list((site_root / "profiles").glob("*.md"))
    assert len(profile_files) > 0


@pytest.mark.e2e
def test_pipeline_respects_mocked_llm_responses(
    whatsapp_fixture,
    smoke_test_config,
    llm_response_mocks,
):
    """Verify that writer agent uses mocked responses."""
    results = run_write_pipeline(smoke_test_config)

    # Check that expected post was generated
    post_slug = "the-license-to-exist-emergent-agency-in-a-test-environment"
    post_file = smoke_test_config.output_dir / "posts" / f"2025-10-28-{post_slug}.md"

    assert post_file.exists(), f"Expected post not found: {post_file}"

    content = post_file.read_text()

    # Verify mock response content is present
    assert "The License to Exist" in content
    assert "emergence" in content
    assert "automation" in content


@pytest.mark.e2e
def test_pipeline_media_enrichment_with_mocks(
    whatsapp_fixture,
    smoke_test_config,
    llm_response_mocks,
):
    """Verify media enrichment with mocked vision responses."""
    results = run_write_pipeline(smoke_test_config)

    # Check media directory
    media_dir = smoke_test_config.output_dir / "media"
    assert media_dir.exists()

    # Verify at least one image was processed
    images_dir = media_dir / "images"
    if images_dir.exists():
        images = list(images_dir.glob("*.jpg"))
        assert len(images) > 0
```

### 4.2 Per-Stage Validation Tests

**File:** `tests/e2e/pipeline/test_pipeline_stages.py`

```python
"""Per-stage validation tests.

Test each pipeline stage independently with mocked dependencies.
"""

@pytest.mark.e2e
def test_ingestion_stage_loads_fixture(whatsapp_fixture):
    """Stage 1: Ingestion - Verify WhatsApp data is loaded."""
    from egregora.input_adapters.whatsapp import WhatsAppAdapter

    adapter = WhatsAppAdapter()
    table = adapter.parse(whatsapp_fixture.zip_path, timezone=whatsapp_fixture.timezone)

    # Verify IR schema
    assert table is not None
    assert "timestamp" in table.schema()
    assert "author" in table.schema()
    assert "message" in table.schema()

    # Verify data loaded
    row_count = table.count().execute()
    assert row_count > 20  # Fixture has ~25 messages


@pytest.mark.e2e
def test_privacy_stage_assigns_uuids(whatsapp_fixture):
    """Stage 2: Privacy - Verify UUID assignment and anonymization."""
    # Load table and apply privacy transformations
    # Verify UUIDs are deterministic and consistent


@pytest.mark.e2e
def test_enrichment_stage_uses_mocks(llm_response_mocks):
    """Stage 3: Enrichment - Verify URL/media enrichment with mocks."""
    # Verify enrichment agent receives mocked responses
    # Verify enrichment table is produced


@pytest.mark.e2e
def test_generation_stage_writes_posts(llm_response_mocks):
    """Stage 4: Generation - Verify writer agent produces posts with mocks."""
    # Verify writer agent is called
    # Verify tool calls use mocked responses
    # Verify posts are generated


@pytest.mark.e2e
def test_publication_stage_persists_output(smoke_test_config):
    """Stage 5: Publication - Verify output is persisted."""
    # Verify MkDocs adapter creates files
    # Verify directory structure is correct
```

### 4.3 Golden Fixture Validation

**File:** `tests/e2e/pipeline/test_golden_fixtures.py` (Refactored)

```python
"""Validate output against golden fixtures.

These tests verify that pipeline output matches the expected
structure and content from tests/fixtures/golden/expected_output/
"""

@pytest.mark.e2e
def test_output_matches_golden_structure(
    whatsapp_fixture,
    smoke_test_config,
    llm_response_mocks,
):
    """Verify output directory structure matches golden."""
    from pathlib import Path

    results = run_write_pipeline(smoke_test_config)

    golden_dir = Path(__file__).parent.parent / "fixtures" / "golden" / "expected_output"
    output_dir = smoke_test_config.output_dir

    # Compare directory structure
    def get_structure(path):
        return sorted([p.relative_to(path).as_posix() for p in path.rglob("*") if p.is_file()])

    golden_files = get_structure(golden_dir)
    output_files = get_structure(output_dir)

    # At minimum, core files should exist
    assert any("posts" in f for f in output_files)
    assert any("profiles" in f for f in output_files)


@pytest.mark.e2e
def test_post_content_matches_golden(smoke_test_config, llm_response_mocks):
    """Verify generated post content matches golden."""
    results = run_write_pipeline(smoke_test_config)

    golden_file = (
        Path(__file__).parent.parent / "fixtures" / "golden" / "expected_output" /
        "posts" / "2025-10-28-the-license-to-exist-emergent-agency-in-a-test-environment.md"
    )

    output_file = (
        smoke_test_config.output_dir /
        "posts" / "2025-10-28-the-license-to-exist-emergent-agency-in-a-test-environment.md"
    )

    assert output_file.exists()

    # Compare content (exact match for deterministic mocks)
    golden_content = golden_file.read_text()
    output_content = output_file.read_text()

    assert golden_content == output_content
```

---

## 5. Mocking Implementation Details

### 5.1 Patching Pydantic-AI Writer Agent

The biggest challenge is intercepting Pydantic-AI agent tool calls. Here are two approaches:

**Approach A: TestModel (Existing)**

Current setup uses `pydantic_ai.models.test.TestModel`:

```python
from pydantic_ai.models import test as pydantic_test

def install_writer_test_model_enhanced(monkeypatch, fixture_responses):
    """Use Pydantic-AI's TestModel to simulate agent behavior."""

    # TestModel allows pre-defining agent responses
    model = pydantic_test.TestModel()

    # Register expected tool calls
    model.tools_definition = [
        # Tool definitions
    ]

    monkeypatch.setattr(
        "egregora.agents.writer.model",
        model,
    )
```

**Approach B: Direct Tool Mock (Simpler)**

Patch the writer agent's tool methods directly:

```python
def mock_write_post_tool(metadata, content):
    """Return mocked post content."""
    return {"path": "posts/2025-10-28-mock-post.md"}

def mock_read_profile_tool(author_uuid):
    """Return mocked profile."""
    return # Mocked profile content

monkeypatch.setattr(
    "egregora.agents.writer.write_post_tool",
    mock_write_post_tool,
)
# ... patch other tools ...
```

### 5.2 GenAI Client Mock Enhancement

Extend existing `MockGeminiClient` with:

```python
class MockGeminiClient:
    """Enhanced mock for realistic responses."""

    def __init__(self, fixture_responses=None):
        self.fixture_responses = fixture_responses or {}
        self.call_count = 0

    def models.generate_content(self, prompt, **kwargs):
        """Return mocked content based on fixture responses."""
        # Analyze prompt to determine response type
        if "enrich" in prompt.lower():
            return self._mock_enrichment_response()
        elif "write_post" in prompt.lower():
            return self._mock_writer_response()
        else:
            return self._mock_generic_response()

    def _mock_enrichment_response(self):
        """Return mocked enrichment JSON."""
        return SimpleNamespace(
            text='{"title": "...", "description": "..."}',
            candidates=[...]
        )

    def _mock_writer_response(self):
        """Return mocked writer agent response."""
        return SimpleNamespace(
            text='{"tool_calls": [...]}',
            candidates=[...]
        )
```

---

## 6. Execution & Validation

### 6.1 Running E2E Tests

```bash
# Run all E2E tests
uv run pytest tests/e2e/ -v --tb=short

# Run smoke test only
uv run pytest tests/e2e/pipeline/test_write_pipeline_e2e.py::test_full_pipeline_smoke_test -v

# Run with timing
uv run pytest tests/e2e/ -v --durations=10

# Run specific stage test
uv run pytest tests/e2e/pipeline/test_pipeline_stages.py::test_ingestion_stage_loads_fixture -v
```

### 6.2 Expected Results

**Smoke Test Execution:**
```
test_full_pipeline_smoke_test PASSED [2.34s]
├─ Ingestion (0.21s)
├─ Privacy (0.15s)
├─ Enrichment (0.52s)
├─ Generation (0.89s)
└─ Publication (0.57s)

Total: < 5 seconds
```

**Golden Fixture Validation:**
```
test_output_matches_golden_structure PASSED [1.02s]
test_post_content_matches_golden PASSED [0.98s]

✓ All output files present
✓ Content matches golden references
```

---

## 7. Extending the Mocks

### 7.1 Adding New Scenarios

To test a new WhatsApp archive:

1. **Add fixture files:**
   ```
   tests/fixtures/my_scenario.zip
   tests/fixtures/golden/my_scenario_expected/
   ```

2. **Create response mocks:**
   ```python
   # tests/e2e/mocks/llm_responses.py

   MY_SCENARIO_URL_ENRICHMENTS = {
       "https://...": URLEnrichmentResponse(...),
   }

   MY_SCENARIO_WRITER_POST = WriterPostResponse(...)
   ```

3. **Add test:**
   ```python
   @pytest.mark.e2e
   def test_my_scenario_pipeline(my_scenario_fixture, llm_response_mocks):
       # Test with new scenario
   ```

### 7.2 Maintaining Golden Fixtures

**When LLM behavior changes:**

1. Run pipeline with real API (once):
   ```bash
   GOOGLE_API_KEY=... uv run pytest test_write_pipeline.py --generate-golden
   ```

2. Review and commit new golden files:
   ```bash
   git diff tests/fixtures/golden/
   git add tests/fixtures/golden/
   git commit -m "Update golden fixtures after LLM change"
   ```

3. Update mocks to match:
   ```python
   # tests/e2e/mocks/llm_responses.py
   FIXTURE_WRITER_POST = WriterPostResponse(
       title="New title from LLM...",
       # ...
   )
   ```

---

## 8. CI/CD Integration

### 8.1 GitHub Actions Workflow

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v2

      - name: Run E2E smoke test
        run: |
          uv sync --all-extras
          uv run pytest tests/e2e/pipeline/test_write_pipeline_e2e.py -v --tb=short
        env:
          GOOGLE_API_KEY: "dummy-key-for-mocks"

      - name: Run stage validation tests
        run: uv run pytest tests/e2e/pipeline/test_pipeline_stages.py -v

      - name: Validate against golden fixtures
        run: uv run pytest tests/e2e/pipeline/test_golden_fixtures.py -v
```

### 8.2 Performance Baseline

Track test execution time to catch regressions:

```python
@pytest.mark.benchmark
def test_pipeline_execution_time(smoke_test_config, llm_response_mocks):
    """Ensure pipeline stays < 5 seconds."""
    import time

    start = time.time()
    run_write_pipeline(smoke_test_config)
    elapsed = time.time() - start

    assert elapsed < 5.0, f"Pipeline took {elapsed:.2f}s (expected < 5.0s)"
```

---

## 9. Success Criteria

### Phase 1: Foundation (Complete this plan)
- [ ] Mock response modules created (llm_responses.py, writer_agent_mocks.py)
- [ ] Fixture-aware responses defined for 5 pipeline stages
- [ ] conftest.py enhanced with llm_response_mocks fixture
- [ ] Golden fixtures validated and documented

### Phase 2: Test Implementation
- [ ] test_write_pipeline_e2e.py implemented (3+ tests)
- [ ] test_pipeline_stages.py implemented (5+ tests, one per stage)
- [ ] test_golden_fixtures.py refactored (3+ tests)
- [ ] All tests pass and execute < 5 seconds

### Phase 3: CI/CD Integration
- [ ] GitHub Actions workflow configured
- [ ] E2E tests run on every PR
- [ ] Performance baselines established
- [ ] Mocks documented in CLAUDE.md

### Phase 4: Documentation & Maintenance
- [ ] Docs/e2e-testing-plan.md finalized
- [ ] Test maintenance guide written
- [ ] Mock response updates documented
- [ ] Golden fixture maintenance procedure documented

---

## 10. Future Enhancements

### VCR Cassette Integration
Record real API responses and replay them:

```python
@pytest.mark.e2e
@vcr.use_cassette("tests/cassettes/writer_agent_call.yaml")
def test_writer_with_real_api(real_api_key):
    """First run records API calls, subsequent runs replay."""
```

### Multi-Scenario Testing
Extend to multiple WhatsApp archives:

```python
@pytest.mark.parametrize("scenario", [
    "whatsapp_sample",
    "slack_integration",
    "tjro_judicial",
    "self_reflection_loop",
])
def test_pipeline_multi_scenario(scenario, llm_response_mocks):
    """Run same pipeline against different input sources."""
```

### Performance Profiling
Identify bottlenecks:

```python
@pytest.mark.profile
def test_pipeline_profiling(profile_config):
    """Generate flame graph of pipeline execution."""
```

---

## 11. References

### Related Files
- **Orchestration:** `src/egregora/orchestration/write_pipeline.py` (main pipeline)
- **Writer Agent:** `src/egregora/agents/writer.py` (post generation)
- **Enricher Agent:** `src/egregora/agents/enricher.py` (URL/media enrichment)
- **Existing Tests:** `tests/e2e/pipeline/test_write_pipeline.py` (reference)
- **Golden Fixtures:** `tests/fixtures/golden/expected_output/` (expected output)

### Dependencies
- `pydantic-ai` - Agent framework with TestModel
- `pytest` - Test runner
- `google-genai` - Gemini API (mocked in tests)
- `ibis` - Dataframe operations

### Configuration
- Mock responses: `tests/e2e/mocks/llm_responses.py` (new)
- Test fixtures: `tests/conftest.py` (enhanced)
- Golden output: `tests/fixtures/golden/expected_output/` (reference)

---

## 12. Questions & Decisions

### Open Questions
1. **Exact match vs. semantic matching?** Should golden fixtures require exact string match or semantic validation?
2. **RAG during E2E?** Should smoke test enable RAG with mocked embeddings, or keep it disabled?
3. **Banner generation?** Should avatar agent be mocked with stub images or actual generation?

### Design Decisions (Proposed)
1. ✅ Use **fixture-aware mocks** (not generic stubs) for realistic validation
2. ✅ **Deterministic responses only** (no randomness in tests)
3. ✅ **Golden fixtures as source of truth** for expected behavior
4. ✅ **Per-stage tests** in addition to full pipeline test for faster debugging
5. ✅ **Target < 5 second execution** for CI/CD feedback speed

---

## 13. Timeline & Ownership

| Phase | Tasks | Est. Effort | Owner |
|-------|-------|------------|-------|
| Plan | This document | ✅ Done | Claude Code |
| Foundation | Mock modules, fixtures | 4 hrs | To assign |
| Implementation | Test modules, validation | 6 hrs | To assign |
| CI/CD | Actions setup, validation | 2 hrs | To assign |
| Docs | Maintenance guide, updates | 1 hr | To assign |
| **Total** | | **13 hrs** | |

---

## 14. Getting Started

To implement this plan:

1. **Create mock modules:**
   ```bash
   touch tests/e2e/mocks/__init__.py
   touch tests/e2e/mocks/llm_responses.py
   touch tests/e2e/mocks/writer_agent_mocks.py
   touch tests/e2e/mocks/enrichment_mocks.py
   ```

2. **Add fixture to conftest:**
   - See section 3.4 for llm_response_mocks fixture code

3. **Implement test modules:**
   - See section 4 for test case implementations

4. **Validate against golden fixtures:**
   - See section 4.3 for golden fixture test

5. **Run and iterate:**
   ```bash
   uv run pytest tests/e2e/pipeline/ -v
   ```

---

**Document Status:** Draft (Ready for Implementation)
**Last Updated:** 2025-11-26
**Next Steps:** Begin Phase 2 (Test Implementation) on `claude/plan-e2e-testing-01SUhmxeLE37R3wYuJ7sbhw5`
