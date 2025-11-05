# Pydantic-AI Migration Plan (Revised)

This document revises the original migration plan with insights from the **Pydantic AI Ecosystem** best practices. The goal remains to refactor Egregora's Gemini integrations to use [Pydantic-AI](https://ai.pydantic.dev/), but now leveraging the full ecosystem including **pydantic-evals** for testing and **pydantic-graph** for complex workflows.

## Key Changes from Original Plan

### 1. Use pydantic-evals for Testing (Not Just TestModel)
Replace manual test stubs with **pydantic-evals** framework for systematic evaluation:
- Create **Dataset** of test cases with expected outputs
- Use **LLM judges** for semantic evaluation (not just exact matches)
- Track regression with **evaluation reports**
- Integrate with **Logfire** for observability

### 2. Leverage pydantic_ai RAG Helpers
Use `pydantic_ai.integrations.rag.rag_context` instead of custom RAG implementation:
- Cleaner integration with agents
- Standard retrieval prompt format
- Better type safety

### 3. Consider pydantic-graph for Complex Workflows
For multi-step workflows (editor iterations, ranking rounds), use **pydantic-graph**:
- State persistence across steps
- Conditional routing
- Visual workflow diagrams
- Resumable execution

### 4. Streaming First
Prioritize streaming responses from the start:
- Use `run_stream()` for all agent calls
- Implement proper async/await patterns
- Handle backpressure appropriately

### 5. Observability from Day One
Integrate Pydantic Logfire throughout:
- Trace all agent calls
- Track token usage and costs
- Monitor evaluation performance
- Debug with production traces

---

## Revised Objectives

1. **Simplify transport** – Drop the `GeminiDispatcher`/`GeminiBatchClient` layer for the new backend
2. **Uniform agent workflow** – Express writer, editor, ranking, and enrichment as Pydantic-AI agents
3. **Systematic testing** – Use `pydantic-evals` for regression testing and quality assurance
4. **RAG via Pydantic helper** – Leverage `rag_context()` for standard retrieval prompts
5. **Stateful workflows** – Use `pydantic-graph` for complex multi-step processes
6. **Recording & replay** – Continue writing transcripts + add eval-based regression tests
7. **Streaming by default** – All agents use `run_stream()` for better UX
8. **Observability** – Integrate Logfire for debugging, monitoring, and cost tracking

---

## Revised Phase-by-Phase Plan

### Phase 0 – Setup & Infrastructure (✅ complete)
- [x] Catalogue every place that imported `google.genai`
- [x] Remove the transport shim (`gemini_transport.py`)
- [x] Build reference test (`tests/test_writer_pydantic_agent.py`)
- [x] Install Pydantic AI ecosystem dependencies

### Phase 1 – Writer Agent with Evals (⚙ in progress)

#### 1.1 Core Agent (✅ mostly complete)
- [x] Implement `write_posts_with_pydantic_agent` with tools
- [x] Provide deterministic tests using `TestModel`
- [ ] **NEW**: Replace `TestModel` with `pydantic-evals` Dataset
- [ ] **NEW**: Add LLM judges for semantic evaluation

#### 1.2 RAG Integration
- [ ] Replace `_query_rag_for_context` with `rag_context()` helper
- [ ] Wrap DuckDB vector store with `find_relevant_docs()` function
- [ ] Update agent tools to use new RAG integration

#### 1.3 Streaming Support
- [ ] Refactor `write_posts_with_pydantic_agent` to use `run_stream()`
- [ ] Handle streaming in CLI (`egregora.orchestration.cli`)
- [ ] Add progress indicators for long-running generations

#### 1.4 Evaluation Suite
- [ ] Create `tests/evals/writer_evals.py` with Dataset
- [ ] Define test cases covering:
  - Empty conversations (should generate no posts)
  - Single-topic conversations (should generate 1 post)
  - Multi-topic conversations (should generate multiple posts)
  - RAG integration (should reference previous posts)
- [ ] Add LLM judges for:
  - Post quality (title, structure, clarity)
  - Metadata accuracy (tags, dates, authors)
  - RAG usage (proper context integration)
- [ ] Run baseline evaluation and establish target scores

#### 1.5 Observability
- [ ] Install `pydantic-ai[logfire]` and `pydantic-evals[logfire]`
- [ ] Configure Logfire integration
- [ ] Add tracing for all agent calls
- [ ] Track token usage and costs per post

### Phase 2 – Editor Agent with Graph Workflow

#### 2.1 Graph Design
- [ ] Design editor workflow as pydantic-graph:
  ```
  AnalyzePost → GenerateEdits → ApplyEdits → ReviewQuality → [MoreEdits | Finish]
  ```
- [ ] Define state schema for editor context
- [ ] Implement conditional routing based on edit quality
- [ ] Add state persistence for resume capability

#### 2.2 Agent Implementation
- [ ] Convert editor to Pydantic Agent with tools:
  - `edit_line` - Modify specific line
  - `full_rewrite` - Complete rewrite
  - `finish` - Complete editing
  - `request_clarification` - Ask user for input
- [ ] Integrate graph workflow with agent
- [ ] Support human-in-the-loop approval for edits

#### 2.3 Streaming Editor
- [ ] Stream edit suggestions as they're generated
- [ ] Show diff preview during streaming
- [ ] Allow interrupt/resume during editing

#### 2.4 Evaluation
- [ ] Create editor evaluation dataset
- [ ] Test cases: grammar fixes, style improvements, clarifications
- [ ] LLM judges for edit quality and appropriateness

### Phase 3 – Ranking & Enrichment

#### 3.1 Ranking Agent
- [ ] Convert Elo ranking to Pydantic Agent
- [ ] Tools: `compare_posts`, `assign_rating`, `get_rankings`
- [ ] Use structured output for comparison results
- [ ] Add streaming for long ranking sessions

#### 3.2 Enrichment as Agent Pipeline
- [ ] Create enrichment agent for media descriptions
- [ ] Create enrichment agent for URL summaries
- [ ] Use pydantic-graph for batch processing:
  ```
  FetchBatch → EnrichItems → ValidateResults → [NextBatch | Complete]
  ```
- [ ] Replace `GeminiBatchClient` with agent-based approach

#### 3.3 Evaluation
- [ ] Create ranking evaluation dataset
- [ ] Test consistency of Elo comparisons
- [ ] Validate enrichment quality for various media types

### Phase 4 – RAG Integration Complete

#### 4.1 Vector Store Wrapper
- [ ] Implement `find_relevant_docs()` satisfying pydantic_ai requirements:
  ```python
  async def find_relevant_docs(
      query: str,
      top_k: int = 5
  ) -> list[dict[str, Any]]:
      """Query DuckDB vector store and return results."""
  ```
- [ ] Integrate with `rag_context()` helper
- [ ] Replace all custom RAG queries

#### 4.2 Context Assembly
- [ ] Use `rag_context()` in writer agent
- [ ] Use `rag_context()` in editor agent
- [ ] Document new RAG approach in code

#### 4.3 RAG Evaluation
- [ ] Create RAG-specific evaluation dataset
- [ ] Test retrieval accuracy and relevance
- [ ] Validate context formatting in prompts

### Phase 5 – Testing & Replay

#### 5.1 Evaluation Infrastructure
- [ ] Create `tests/evals/` directory structure
- [ ] Organize datasets by agent type (writer, editor, ranking)
- [ ] Implement regression test suite using recorded transcripts
- [ ] Set up CI to run evals on every PR

#### 5.2 Recording & Replay
- [ ] Add utility to record message logs on demand
- [ ] Implement replay via `FunctionModel` in tests
- [ ] CLI flags: `--record`, `--replay <file>`, `--eval-mode`
- [ ] Documentation for recording/replay workflow

#### 5.3 Continuous Evaluation
- [ ] Run evaluation suite in CI
- [ ] Track eval scores over time (Logfire dashboard)
- [ ] Alert on regression (score drops > 10%)
- [ ] Generate evaluation reports for PRs

### Phase 6 – Cleanup & Documentation

#### 6.1 Code Cleanup
- [ ] Remove unused dispatcher/batch code
- [ ] Clean up legacy backend path (keep behind flag temporarily)
- [ ] Consolidate duplicate utilities
- [ ] Update type hints and docstrings

#### 6.2 Documentation
- [ ] Update README with new backend instructions
- [ ] Developer guide for Pydantic AI patterns
- [ ] Migration guide for contributors
- [ ] Architecture diagrams (mermaid from pydantic-graph)

#### 6.3 Environment & Config
- [ ] Document environment variables:
  - `EGREGORA_LLM_BACKEND=pydantic` (new backend)
  - `EGREGORA_LLM_BACKEND=legacy` (old backend)
  - `LOGFIRE_TOKEN=...` (observability)
- [ ] Add config validation
- [ ] Provide migration script for existing users

---

## New Implementation Patterns

### Pattern 1: Agent with Evals
```python
from pydantic_ai import Agent
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import LLMJudge

# Create agent
agent = Agent('gemini-1.5-pro', ...)

# Define evaluation dataset
dataset = Dataset(
    cases=[
        Case(
            name='empty_conversation',
            inputs='<empty conversation>',
            expected_output={'posts': 0, 'summary': 'No content'}
        ),
    ],
    evaluators=[
        LLMJudge(
            model='gemini-1.5-flash',
            prompt='Evaluate if the agent correctly handled the input.'
        )
    ]
)

# Run evaluation
async def run_agent(input: str) -> dict:
    result = await agent.run(input)
    return result.output

report = await dataset.evaluate(run_agent)
```

### Pattern 2: Graph-Based Workflow
```python
from dataclasses import dataclass
from pydantic_graph import BaseNode, End, Graph, GraphRunContext

@dataclass
class EditorState:
    post_content: str
    edits_made: list[str]
    quality_score: float

@dataclass
class AnalyzePost(BaseNode):
    async def run(self, ctx: GraphRunContext[EditorState]) -> 'GenerateEdits':
        # Agent analyzes post
        return GenerateEdits()

@dataclass
class GenerateEdits(BaseNode):
    async def run(self, ctx: GraphRunContext[EditorState]) -> 'ReviewQuality':
        # Agent generates edit suggestions
        return ReviewQuality()

@dataclass
class ReviewQuality(BaseNode):
    async def run(self, ctx: GraphRunContext[EditorState]) -> 'GenerateEdits | End':
        if ctx.state.quality_score < 0.8:
            return GenerateEdits()  # More edits needed
        return End()  # Done

# Run graph
graph = Graph(nodes=[AnalyzePost, GenerateEdits, ReviewQuality])
state = EditorState(post_content="...", edits_made=[], quality_score=0.0)
await graph.run(AnalyzePost(), state=state)
```

### Pattern 3: Streaming Agent
```python
from pydantic_ai import Agent

agent = Agent('gemini-1.5-pro', ...)

async with agent.run_stream('Generate post about AI') as response:
    async for chunk in response.stream_text():
        print(chunk, end='', flush=True)

# Get final structured output
result = await response.get_result()
```

### Pattern 4: RAG Integration
```python
from pydantic_ai import Agent
from pydantic_ai.integrations.rag import rag_context

async def find_relevant_docs(query: str, top_k: int = 5) -> list[dict]:
    # Query DuckDB vector store
    store = VectorStore(rag_dir / "chunks.parquet")
    results = store.search(query_vector, top_k=top_k)
    return results.execute().to_dict('records')

agent = Agent('gemini-1.5-pro', ...)

@agent.tool
async def search_context(ctx, query: str) -> str:
    """Retrieve relevant context from past posts."""
    docs = await find_relevant_docs(query)
    return rag_context(docs)
```

---

## Dependencies Update

Update `pyproject.toml`:

```toml
dependencies = [
    # ... existing deps ...
    "pydantic-ai>=0.0.14",
    "pydantic-evals>=0.0.1",
    "pydantic-graph>=0.0.1",
]

[project.optional-dependencies]
observability = [
    "pydantic-ai[logfire]",
    "pydantic-evals[logfire]",
]
```

---

## Success Metrics

### Code Quality
- [ ] All agents use Pydantic AI patterns
- [ ] Test coverage > 90% with pydantic-evals
- [ ] Zero usage of legacy dispatcher/batch code in new backend
- [ ] All workflows visualizable with pydantic-graph diagrams

### Performance
- [ ] Agent response latency < 2s for simple queries
- [ ] Streaming starts within 500ms
- [ ] Token usage tracked for all calls
- [ ] Cost per post < $0.05

### Evaluation Scores
- [ ] Writer agent: > 0.85 average score
- [ ] Editor agent: > 0.90 average score
- [ ] Ranking agent: > 0.80 consistency score
- [ ] RAG retrieval: > 0.75 relevance score

### Observability
- [ ] All agent calls traced in Logfire
- [ ] Cost dashboard available
- [ ] Error rate < 1% in production
- [ ] Evaluation runs tracked over time

---

## Migration Timeline

**Estimated Timeline: 6-8 weeks**

- **Weeks 1-2**: Phase 1 (Writer + Evals + RAG)
- **Weeks 3-4**: Phase 2 (Editor + Graph)
- **Week 5**: Phase 3 (Ranking + Enrichment)
- **Week 6**: Phase 4 (RAG Complete)
- **Week 7**: Phase 5 (Testing + Replay)
- **Week 8**: Phase 6 (Cleanup + Docs)

---

## Pydantic Logfire Integration

### Overview
**Pydantic Logfire** (https://pydantic.dev/logfire) is the observability platform built specifically for Pydantic AI applications. It provides real-time debugging, cost tracking, and performance monitoring.

### Setup

#### 1. Installation
```bash
uv add 'pydantic-ai[logfire]' 'pydantic-evals[logfire]'
```

#### 2. Configuration
```python
import logfire

# Configure once at application startup
logfire.configure()
```

#### 3. Environment Variables
```bash
# Add to .envrc
export LOGFIRE_TOKEN="your-token-here"

# Reload environment
direnv allow
```

### Integration Points

#### Agent Tracing
All agent calls are automatically traced:
```python
import logfire
from pydantic_ai import Agent

logfire.configure()

agent = Agent('gemini-1.5-pro')

# Automatically traced with full context
with logfire.span('user_query', query_type='post_generation'):
    result = await agent.run(prompt)
    logfire.info(
        'Generated posts',
        count=len(result.saved_posts),
        tokens=result.usage().total_tokens
    )
```

#### Evaluation Tracking
Track eval runs and scores over time:
```python
from pydantic_evals import Dataset
import logfire

logfire.configure()

# Run with Logfire tracking
report = await dataset.evaluate(run_agent, logfire=True)

# Scores automatically logged to Logfire dashboard
```

#### Cost Monitoring
Track token usage and costs:
```python
result = await agent.run(prompt)

logfire.info(
    'Agent completed',
    tokens_total=result.usage().total_tokens,
    tokens_prompt=result.usage().prompt_tokens,
    tokens_completion=result.usage().completion_tokens,
    estimated_cost=result.cost()
)
```

### Dashboards

Once configured, access dashboards at https://logfire.pydantic.dev:
- **Traces**: See all agent calls with full context
- **Costs**: Track token usage and estimated costs per agent/period
- **Evals**: Monitor evaluation scores over time
- **Errors**: Debug failures with full stack traces

### Egregora-Specific Integration

#### Writer Agent
```python
# src/egregora/generation/writer/pydantic_agent.py
import logfire

logfire.configure()

def write_posts_with_pydantic_agent(...):
    with logfire.span('writer_agent', period=period_date):
        result = agent.run_sync(prompt, deps=state)

        logfire.info(
            'Writer completed',
            period=period_date,
            posts_created=len(state.saved_posts),
            profiles_updated=len(state.saved_profiles),
            tokens=result.usage().total_tokens
        )
```

#### Editor Agent
```python
# Track editing iterations
with logfire.span('editor_session', post_slug=post_slug):
    for iteration in range(max_iterations):
        with logfire.span('edit_iteration', iteration=iteration):
            result = await agent.run(edit_prompt)
            logfire.info('Edit applied', changes=len(edits))
```

#### RAG Queries
```python
# Track retrieval performance
with logfire.span('rag_query', query_type='similar_posts'):
    results = store.search(query_vector, top_k=5)
    logfire.info(
        'RAG retrieval',
        results_count=len(results),
        avg_similarity=results['similarity'].mean()
    )
```

### CI Integration

Run evals in CI with Logfire tracking:
```yaml
# .github/workflows/test.yml
- name: Run Evaluations
  env:
    LOGFIRE_TOKEN: ${{ secrets.LOGFIRE_TOKEN }}
  run: |
    uv run pytest tests/evals/ --logfire
```

### Alerts

Configure alerts in Logfire dashboard:
- **Eval score drops > 10%**: Alert on regression
- **Cost spike**: Alert if daily cost exceeds threshold
- **Error rate > 1%**: Alert on failures

---

## Next Immediate Actions

1. **Install pydantic-evals**: `uv add pydantic-evals`
2. **Set up Logfire**:
   - Create account at https://pydantic.dev/logfire
   - Get token and add to `.envrc`
   - Run `logfire.configure()` in code
3. **Create writer evaluation dataset** in `tests/evals/writer_evals.py`
4. **Run baseline evaluation with Logfire** and establish target scores
5. **Replace `_query_rag_for_context`** with `rag_context()` helper
6. **Add streaming support** to writer agent
7. **Set up Logfire dashboards** for monitoring

---

## References

- **Pydantic AI Docs**: https://ai.pydantic.dev/
- **Pydantic Evals**: https://ai.pydantic.dev/evals/
- **Pydantic Graph**: https://ai.pydantic.dev/graph/
- **Workspace Skill**: `/home/frank/workspace/.claude/skills/pydantic-ai-ecosystem/SKILL.md`

---

## Notes

- Keep legacy backend available during migration with `EGREGORA_LLM_BACKEND` flag
- All new code should follow Pydantic AI ecosystem patterns
- Prioritize observability and evaluation from the start
- Use streaming for better UX in interactive tools (editor, writer CLI)
