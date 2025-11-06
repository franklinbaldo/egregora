# Pydantic AI Ecosystem Skill

## Overview

This skill provides comprehensive guidance for working with the Pydantic AI ecosystem, a suite of Python libraries for building production-grade AI agents, workflows, and evaluations with type safety and observability.

## Ecosystem Components

### 1. **pydantic-ai** - GenAI Agent Framework
The core framework for building AI agents with type safety and observability.

**Official Documentation**: https://ai.pydantic.dev/
**GitHub**: https://github.com/pydantic/pydantic-ai
**PyPI**: https://pypi.org/project/pydantic-ai/

### 2. **pydantic-evals** - Evaluation Framework
Systematic testing and evaluation of AI systems from simple LLM calls to complex multi-agent applications.

**Official Documentation**: https://ai.pydantic.dev/evals/
**PyPI**: https://pypi.org/project/pydantic-evals/

### 3. **pydantic-graph** - Graph/State Machine Library
Define async graphs and state machines using Python type hints for complex workflows.

**Official Documentation**: https://ai.pydantic.dev/graph/
**PyPI**: https://pypi.org/project/pydantic-graph/

### 4. **fasta2a** - Agent-to-Agent (A2A) Protocol
Framework-agnostic implementation of the A2A protocol for agent interoperability.

**Official Documentation**: https://ai.pydantic.dev/api/fasta2a/
**GitHub**: https://github.com/pydantic/fasta2a
**A2A Protocol**: https://ai.pydantic.dev/a2a/

---

## Installation

### Full Installation (All Components)
```bash
# Using pip
pip install pydantic-ai pydantic-evals pydantic-graph

# Using uv (recommended for this workspace)
uv add pydantic-ai pydantic-evals pydantic-graph

# With Logfire observability
uv add 'pydantic-ai[logfire]' 'pydantic-evals[logfire]'
```

### Minimal Installation
```bash
# Just pydantic-ai (includes pydantic-graph as dependency)
uv add pydantic-ai

# Add evals separately if needed
uv add pydantic-evals
```

---

## 1. Pydantic AI - Agent Framework

### Key Features
- **Model-agnostic**: Supports OpenAI, Anthropic, Gemini, Mistral, Ollama, and 20+ providers
- **Type-safe**: Full IDE autocomplete and type checking
- **Observability**: Integrates with Pydantic Logfire for debugging and monitoring
- **Tools**: Register Python functions as agent tools
- **Structured outputs**: Validate responses with Pydantic models
- **Streaming**: Stream responses token-by-token
- **Dependency injection**: Pass context and dependencies to agents

### Quick Start

#### Basic Agent
```python
from pydantic_ai import Agent

# Create agent with model and instructions
agent = Agent(
    'anthropic:claude-sonnet-4-0',  # or 'openai:gpt-4', 'gemini-1.5-pro', etc.
    instructions='Be concise, reply with one sentence.'
)

# Run synchronously
result = agent.run_sync('Where does "hello world" come from?')
print(result.output)

# Run asynchronously
result = await agent.run('Explain quantum computing')
print(result.output)
```

#### Agent with Tools
```python
from pydantic_ai import Agent, RunContext
import httpx

# Define agent with dependency type
agent = Agent(
    'openai:gpt-4',
    instructions='Use the weather tool to answer questions about weather.',
    deps_type=httpx.AsyncClient
)

@agent.tool
async def get_weather(ctx: RunContext[httpx.AsyncClient], city: str) -> dict:
    """Get current weather for a city."""
    response = await ctx.deps.get(f'https://api.weather.com/{city}')
    return response.json()

# Use agent with dependencies
async with httpx.AsyncClient() as client:
    result = await agent.run('What is the weather in Paris?', deps=client)
    print(result.output)
```

#### Structured Output
```python
from pydantic import BaseModel
from pydantic_ai import Agent

class CityInfo(BaseModel):
    name: str
    country: str
    population: int
    famous_for: list[str]

agent = Agent(
    'gemini-1.5-pro',
    result_type=CityInfo,
    instructions='Extract structured city information.'
)

result = agent.run_sync('Tell me about Tokyo')
city: CityInfo = result.output
print(f"{city.name}, {city.country} - Population: {city.population:,}")
```

#### Streaming Responses
```python
from pydantic_ai import Agent

agent = Agent('anthropic:claude-sonnet-4-0')

async with agent.run_stream('Write a haiku about coding') as response:
    async for chunk in response.stream_text():
        print(chunk, end='', flush=True)
```

### Model Configuration
```python
from pydantic_ai import Agent
from pydantic_ai.models import ModelSettings

agent = Agent(
    'openai:gpt-4',
    model_settings=ModelSettings(
        temperature=0.7,
        max_tokens=1000,
        top_p=0.9
    )
)
```

### Environment Variables for API Keys
```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# Google Gemini
export GOOGLE_API_KEY="..."
export GEMINI_API_KEY="..."  # Alternative

# Set in .envrc for this workspace
```

---

## 2. Pydantic Evals - Evaluation Framework

### Key Features
- **Code-first**: Define evaluations entirely in Python
- **Built-in evaluators**: Exact match, type checking, custom logic
- **LLM as a judge**: Use LLMs to evaluate subjective qualities
- **Span-based evaluation**: Analyze internal agent behavior via traces
- **Logfire integration**: Visualize results and track experiments

### Core Concepts
- **Case**: Single test scenario with inputs and expected outputs
- **Dataset**: Collection of test cases
- **Evaluator**: Function that scores task results
- **Experiment**: Running cases against a task

### Quick Start

#### Basic Evaluation
```python
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance, ExactMatch

# Define test cases
cases = [
    Case(
        name='capital_france',
        inputs='What is the capital of France?',
        expected_output='Paris'
    ),
    Case(
        name='capital_japan',
        inputs='What is the capital of Japan?',
        expected_output='Tokyo'
    ),
]

# Create dataset with evaluators
dataset = Dataset(
    cases=cases,
    evaluators=[
        IsInstance(type_name='str'),
        ExactMatch()
    ]
)

# Define task to evaluate
async def guess_capital(question: str) -> str:
    # Your LLM call or agent here
    if 'France' in question:
        return 'Paris'
    elif 'Japan' in question:
        return 'Tokyo'
    return 'Unknown'

# Run evaluation
report = await dataset.evaluate(guess_capital)
report.print()
```

#### Evaluating Pydantic AI Agents
```python
from pydantic_ai import Agent
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import LLMJudge

# Create agent
agent = Agent(
    'anthropic:claude-sonnet-4-0',
    instructions='Answer geography questions concisely.'
)

# Define cases
cases = [
    Case(
        name='geography_1',
        inputs='What is the capital of Germany?',
        expected_output='Berlin'
    ),
    Case(
        name='geography_2',
        inputs='What is the largest ocean?',
        expected_output='Pacific Ocean'
    ),
]

# Create dataset with LLM judge
dataset = Dataset(
    cases=cases,
    evaluators=[
        LLMJudge(
            model='openai:gpt-4',
            prompt='Does the answer correctly match the expected output? Consider semantic equivalence.'
        )
    ]
)

# Task wrapper for agent
async def run_agent(question: str) -> str:
    result = await agent.run(question)
    return result.output

# Evaluate
report = await dataset.evaluate(run_agent)
report.print()
```

#### Custom Evaluators
```python
from pydantic_evals import Evaluator, EvalResult

class ContainsKeyword(Evaluator):
    def __init__(self, keyword: str):
        self.keyword = keyword

    async def evaluate(self, case, result, **kwargs) -> EvalResult:
        score = 1.0 if self.keyword.lower() in result.output.lower() else 0.0
        return EvalResult(
            score=score,
            reason=f"Keyword '{self.keyword}' {'found' if score == 1.0 else 'not found'}"
        )

# Use in dataset
dataset = Dataset(
    cases=[...],
    evaluators=[ContainsKeyword('climate')]
)
```

#### Logfire Integration
```bash
# Install with Logfire support
uv add 'pydantic-evals[logfire]'
```

```python
import logfire
from pydantic_evals import Dataset

# Configure Logfire
logfire.configure()

# Run evaluations - automatically logs to Logfire
report = await dataset.evaluate(task, logfire=True)

# View results at https://logfire.pydantic.dev
```

---

## 3. Pydantic Graph - State Machine Library

### Key Features
- **Type-safe graphs**: Define nodes and edges with type hints
- **Async execution**: Built for async/await workflows
- **State persistence**: Snapshot and resume graph execution
- **Dependency injection**: Pass external dependencies to nodes
- **Visual diagrams**: Generate Mermaid diagrams automatically

### Core Concepts
- **Node**: Dataclass with a `run` method
- **Graph**: Collection of connected nodes
- **GraphRunContext**: Holds state and dependencies
- **End**: Signal to terminate graph execution

### Quick Start

#### Simple Graph
```python
from dataclasses import dataclass
from pydantic_graph import BaseNode, End, Graph

@dataclass
class StartNode(BaseNode):
    async def run(self, ctx) -> 'ProcessNode':
        print("Starting workflow")
        return ProcessNode()

@dataclass
class ProcessNode(BaseNode):
    async def run(self, ctx) -> 'EndNode':
        print("Processing data")
        return EndNode()

@dataclass
class EndNode(BaseNode):
    async def run(self, ctx) -> End:
        print("Workflow complete")
        return End()

# Create and run graph
graph = Graph(nodes=[StartNode, ProcessNode, EndNode])
result = await graph.run(StartNode())
```

#### Conditional Routing
```python
from dataclasses import dataclass
from pydantic_graph import BaseNode, End, Graph

@dataclass
class CheckCondition(BaseNode):
    value: int

    async def run(self, ctx) -> 'PathA | PathB':
        if self.value > 10:
            return PathA()
        return PathB()

@dataclass
class PathA(BaseNode):
    async def run(self, ctx) -> End:
        print("Taking path A")
        return End()

@dataclass
class PathB(BaseNode):
    async def run(self, ctx) -> End:
        print("Taking path B")
        return End()

# Run with different inputs
graph = Graph(nodes=[CheckCondition, PathA, PathB])
await graph.run(CheckCondition(value=15))  # Takes PathA
await graph.run(CheckCondition(value=5))   # Takes PathB
```

#### Graph with State
```python
from dataclasses import dataclass, field
from pydantic_graph import BaseNode, End, Graph, GraphRunContext

@dataclass
class WorkflowState:
    count: int = 0
    messages: list[str] = field(default_factory=list)

@dataclass
class IncrementNode(BaseNode):
    async def run(self, ctx: GraphRunContext[WorkflowState]) -> 'CheckNode':
        ctx.state.count += 1
        ctx.state.messages.append(f"Count is now {ctx.state.count}")
        return CheckNode()

@dataclass
class CheckNode(BaseNode):
    async def run(self, ctx: GraphRunContext[WorkflowState]) -> 'IncrementNode | End':
        if ctx.state.count < 3:
            return IncrementNode()
        return End()

# Run with state
graph = Graph(nodes=[IncrementNode, CheckNode])
state = WorkflowState()
result = await graph.run(IncrementNode(), state=state)
print(state.messages)  # ['Count is now 1', 'Count is now 2', 'Count is now 3']
```

#### Generating Graph Diagrams
```python
from pydantic_graph import Graph

graph = Graph(nodes=[StartNode, ProcessNode, EndNode])

# Generate Mermaid diagram
mermaid = graph.mermaid()
print(mermaid)

# Output can be visualized at https://mermaid.live
```

---

## 4. fasta2a - Agent-to-Agent (A2A) Protocol

### Overview
The Agent-to-Agent (A2A) Protocol is an open standard by Google that enables communication and interoperability between AI agents, regardless of framework or vendor. **fasta2a** is Pydantic's framework-agnostic implementation of this protocol in Python.

### Key Features
- **Agent Interoperability**: Standardized communication between agents from different frameworks
- **Context Management**: Maintains conversation continuity across agent interactions
- **Task Management**: Track task states (submitted, working, completed, failed)
- **Protocol Compliance**: Implements A2A protocol version 0.2.5+
- **Easy Integration**: One-line conversion of Pydantic AI agents to A2A servers

### Quick Start

#### Convert Agent to A2A Server
```python
from pydantic_ai import Agent

# Create regular Pydantic AI agent
agent = Agent(
    'openai:gpt-4',
    instructions='Be helpful and concise.'
)

# Convert to A2A server (FastAPI app)
app = agent.to_a2a()

# Run with: uvicorn my_agent:app --host 0.0.0.0 --port 8000
```

#### A2A Protocol Communication
```python
import httpx

# Client communicating with A2A server
async with httpx.AsyncClient() as client:
    # Start new conversation (no context_id)
    response = await client.post(
        'http://localhost:8000/agent',
        json={
            'message': 'Hello, agent!',
            'context_id': None  # New conversation
        }
    )

    context_id = response.json()['context_id']

    # Continue conversation (with context_id)
    response = await client.post(
        'http://localhost:8000/agent',
        json={
            'message': 'Follow up question',
            'context_id': context_id  # Continue conversation
        }
    )
```

#### Agent Card (Describe Capabilities)
```python
from pydantic_ai import Agent
from fasta2a import AgentCard, Skill

agent = Agent('gemini-1.5-pro')

# Define agent capabilities
card = AgentCard(
    name="My Research Agent",
    description="An agent that helps with research tasks",
    skills=[
        Skill(
            name="web_search",
            description="Search the web for information"
        ),
        Skill(
            name="summarize",
            description="Summarize long documents"
        )
    ]
)

app = agent.to_a2a(agent_card=card)
```

### Task Management

#### Submit and Track Tasks
```python
from fasta2a import Task, TaskStatus

# Task is submitted to agent
task = Task(
    id="task-123",
    status=TaskStatus.SUBMITTED,
    input="Write a blog post about AI",
    artifacts=[]
)

# Agent updates task status
task.status = TaskStatus.WORKING

# Agent completes task with artifacts
task.status = TaskStatus.COMPLETED
task.artifacts = [
    {
        "type": "text/markdown",
        "content": "# AI Blog Post\n\n..."
    }
]
```

### Storage Architecture

#### Context Storage
Stores conversation context in format optimized for agent implementation:
```python
from fasta2a import ContextStorage

# Context includes conversation history
context = {
    "context_id": "ctx-123",
    "messages": [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"}
    ]
}
```

#### Task Storage
Stores tasks in A2A protocol format:
```python
from fasta2a import TaskStorage

# Task with full history
task_data = {
    "task_id": "task-123",
    "status": "completed",
    "artifacts": [...],
    "history": [...]
}
```

### When to Use A2A Protocol

Use **fasta2a** when:
- Building multi-agent systems with agents from different frameworks
- Creating agent marketplaces or registries
- Need standardized agent-to-agent communication
- Want to expose agents as interoperable services
- Building agent orchestration platforms

**Note**: A2A protocol is for agent-to-agent communication, not for building general web APIs. For REST APIs with Pydantic AI agents, use FastAPI directly (see examples in Common Patterns section).

---

## Common Patterns

### 1. Agent with Evals
```python
from pydantic_ai import Agent
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import LLMJudge

# Create agent
agent = Agent('anthropic:claude-sonnet-4-0')

# Create evaluation dataset
dataset = Dataset(
    cases=[
        Case(name='test1', inputs='Question 1', expected_output='Answer 1'),
        Case(name='test2', inputs='Question 2', expected_output='Answer 2'),
    ],
    evaluators=[LLMJudge(model='openai:gpt-4')]
)

# Evaluate agent
async def run_agent(question: str) -> str:
    result = await agent.run(question)
    return result.output

report = await dataset.evaluate(run_agent)
report.print()
```

### 2. Graph-based Agent Workflow
```python
from dataclasses import dataclass
from pydantic_ai import Agent
from pydantic_graph import BaseNode, End, Graph, GraphRunContext

@dataclass
class AgentState:
    user_query: str
    analysis: str = ""
    response: str = ""

agent = Agent('openai:gpt-4')

@dataclass
class AnalyzeNode(BaseNode):
    async def run(self, ctx: GraphRunContext[AgentState]) -> 'GenerateNode':
        result = await agent.run(f"Analyze this query: {ctx.state.user_query}")
        ctx.state.analysis = result.output
        return GenerateNode()

@dataclass
class GenerateNode(BaseNode):
    async def run(self, ctx: GraphRunContext[AgentState]) -> End:
        result = await agent.run(
            f"Based on this analysis: {ctx.state.analysis}, generate a response"
        )
        ctx.state.response = result.output
        return End()

# Run graph
graph = Graph(nodes=[AnalyzeNode, GenerateNode])
state = AgentState(user_query="How do I build an AI agent?")
await graph.run(AnalyzeNode(), state=state)
print(state.response)
```

### 3. FastAPI + Agent + Evals
```python
from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_evals import Case, Dataset

app = FastAPI()
agent = Agent('gemini-1.5-pro')

# Store evaluation results
evals_dataset = Dataset(cases=[], evaluators=[])

class Query(BaseModel):
    question: str

@app.post("/ask")
async def ask(query: Query):
    result = await agent.run(query.question)

    # Log for evaluation
    evals_dataset.cases.append(
        Case(name=f"query_{len(evals_dataset.cases)}", inputs=query.question)
    )

    return {"answer": result.output}

@app.post("/evaluate")
async def evaluate():
    async def run_agent(q: str) -> str:
        r = await agent.run(q)
        return r.output

    report = await evals_dataset.evaluate(run_agent)
    return report.to_dict()
```

---

## Best Practices

### 1. Type Safety
- Always specify `deps_type` for agents with dependencies
- Use Pydantic models for structured outputs
- Leverage type hints for graph nodes

### 2. Error Handling
```python
from pydantic_ai import Agent, ModelRetry

agent = Agent('openai:gpt-4')

@agent.tool
async def fetch_data(ctx, url: str) -> str:
    try:
        # Fetch data
        return data
    except Exception as e:
        # Retry with context
        raise ModelRetry(f"Failed to fetch: {e}")

result = await agent.run('Get data from https://example.com')
```

### 3. Observability with Logfire
```python
import logfire
from pydantic_ai import Agent

logfire.configure()

agent = Agent('anthropic:claude-sonnet-4-0')

# Automatically traced
with logfire.span('user_query'):
    result = await agent.run('Question')
```

### 4. Testing
```python
import pytest
from pydantic_ai import Agent
from pydantic_evals import Case, Dataset

@pytest.fixture
def agent():
    return Agent('openai:gpt-4')

@pytest.fixture
def eval_dataset():
    return Dataset(cases=[
        Case(name='test1', inputs='Q1', expected_output='A1'),
    ])

@pytest.mark.asyncio
async def test_agent(agent, eval_dataset):
    async def run(q: str) -> str:
        r = await agent.run(q)
        return r.output

    report = await eval_dataset.evaluate(run)
    assert report.average_score() > 0.8
```

### 5. Cost Management
```python
from pydantic_ai import Agent, RunContext

agent = Agent('openai:gpt-4')

result = await agent.run('Question')

# Access usage info
print(f"Tokens: {result.usage().total_tokens}")
print(f"Cost estimate: ${result.cost()}")
```

---

## Environment Setup for This Workspace

### 1. Install Dependencies
```bash
cd /home/frank/workspace
uv add pydantic-ai pydantic-evals pydantic-graph fastapi uvicorn
```

### 2. Configure API Keys in `.envrc`
```bash
# Add to /home/frank/workspace/.envrc
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="$GEMINI_API_KEY"  # Already configured

# Reload
direnv allow
```

### 3. Example Project Structure
```
my_ai_project/
├── agents/
│   ├── __init__.py
│   └── main_agent.py      # Pydantic AI agents
├── evals/
│   ├── __init__.py
│   └── test_cases.py      # Evaluation datasets
├── workflows/
│   ├── __init__.py
│   └── graphs.py          # Pydantic Graph workflows
├── api/
│   ├── __init__.py
│   └── app.py             # FastAPI application
├── tests/
│   └── test_agents.py
└── pyproject.toml
```

---

## Resources

### Documentation
- **Pydantic AI**: https://ai.pydantic.dev/
- **Pydantic Evals**: https://ai.pydantic.dev/evals/
- **Pydantic Graph**: https://ai.pydantic.dev/graph/
- **Pydantic Logfire**: https://logfire.pydantic.dev/

### Examples
- **Chat App**: https://ai.pydantic.dev/examples/chat-app/
- **GitHub Repository**: https://github.com/pydantic/pydantic-ai

### Community
- **GitHub Discussions**: https://github.com/pydantic/pydantic-ai/discussions
- **Pydantic Slack**: Join via pydantic.dev

---

## Troubleshooting

### API Key Issues
```bash
# Check if keys are set
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY
echo $GOOGLE_API_KEY

# Test connection
uv run python -c "from pydantic_ai import Agent; Agent('openai:gpt-4').run_sync('test')"
```

### Import Errors
```bash
# Reinstall
uv add --force-reinstall pydantic-ai

# Check installation
uv pip list | grep pydantic
```

### Performance Issues
- Use streaming for long responses
- Enable async execution
- Monitor with Logfire
- Use `pydantic-ai-slim` for reduced dependencies

---

## When to Use Each Component

### Use **pydantic-ai** when:
- Building AI agents with tools
- Need type-safe LLM interactions
- Want observability and debugging
- Integrating multiple models

### Use **pydantic-evals** when:
- Testing agent accuracy
- Running regression tests
- Comparing model outputs
- Evaluating agent behavior

### Use **pydantic-graph** when:
- Complex multi-step workflows
- State machine requirements
- Conditional agent routing
- Need resumable execution

### Use **fasta2a** when:
- Building multi-agent systems
- Need agent-to-agent communication
- Want framework-agnostic interoperability
- Creating agent marketplaces

**Note**: For building REST APIs with agents, use FastAPI directly - not fasta2a. See Common Patterns for FastAPI examples.

---

## Version Information

This skill was created with documentation from:
- **pydantic-ai**: Latest (1.9.1+, Oct 2025)
- **pydantic-evals**: Latest (Q1 2025 release)
- **pydantic-graph**: Latest (included with pydantic-ai)

Always check official documentation for latest features and updates.
