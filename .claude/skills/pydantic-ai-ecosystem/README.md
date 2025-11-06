# Pydantic AI Ecosystem Skill

A comprehensive Claude Code skill for working with the Pydantic AI ecosystem: **pydantic-ai**, **pydantic-evals**, **pydantic-graph**, and **FastAPI integration**.

## Quick Start

### Installation
```bash
# Install all components
uv add pydantic-ai pydantic-evals pydantic-graph fastapi uvicorn

# With Logfire observability
uv add 'pydantic-ai[logfire]' 'pydantic-evals[logfire]'
```

### Set API Keys
```bash
# Add to .envrc or export directly
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."  # For Gemini
```

### Run Examples

#### 1. Basic Agent
```bash
python example_agent.py
```

Creates an agent with tools and structured output using Pydantic models.

#### 2. Evaluations
```bash
python example_evals.py
```

Demonstrates testing and evaluating AI agents with test cases and LLM judges.

#### 3. Graph Workflows
```bash
python example_graph.py
```

Shows state machine workflows with conditional routing and state persistence.

#### 4. Agent-to-Agent (A2A) Protocol
```bash
uvicorn example_fasta2a:app --reload
```

Then test:
```bash
# Get agent capabilities
curl http://localhost:8000/agent-card

# Send message to agent
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather in Paris?"}'
```

## What's Included

### Files
- **SKILL.md** - Complete documentation with all patterns and best practices
- **example_agent.py** - Agent with tools and structured output
- **example_evals.py** - Evaluation framework usage
- **example_graph.py** - State machine workflows
- **example_fasta2a.py** - Agent-to-Agent (A2A) protocol server

### Coverage
- ✅ All 4 ecosystem components (pydantic-ai, pydantic-evals, pydantic-graph, fasta2a)
- ✅ Installation and setup
- ✅ Common patterns and best practices (including FastAPI integration)
- ✅ Integration examples
- ✅ Error handling and testing
- ✅ Workspace-specific configuration

## Documentation Structure

Read `SKILL.md` for:
1. **Overview** - Ecosystem components and features
2. **Installation** - Setup for different use cases
3. **Pydantic AI** - Agent framework with tools and streaming
4. **Pydantic Evals** - Testing and evaluation patterns
5. **Pydantic Graph** - State machine workflows
6. **FastAPI Integration** - Building production APIs
7. **Common Patterns** - Real-world integration examples
8. **Best Practices** - Type safety, error handling, observability
9. **Troubleshooting** - Common issues and solutions

## Key Features

### Type Safety
All components leverage Python type hints for IDE autocomplete and validation.

### Model Agnostic
Works with OpenAI, Anthropic, Google Gemini, Mistral, Ollama, and 20+ providers.

### Observability
Integrates with Pydantic Logfire for debugging, monitoring, and cost tracking.

### Async First
Built for async/await with streaming support and high performance.

## When to Use This Skill

Use this skill when:
- Building AI agents with tools and structured outputs
- Evaluating and testing LLM applications
- Creating complex multi-step AI workflows
- Building production APIs (with FastAPI examples in SKILL.md)
- Enabling agent-to-agent communication
- Migrating from other agent frameworks
- Need type-safe LLM interactions

## Resources

- **Official Docs**: https://ai.pydantic.dev/
- **GitHub**: https://github.com/pydantic/pydantic-ai
- **Examples**: See `example_*.py` files in this directory

## Workspace Integration

This skill is configured for use in `/home/frank/workspace` with:
- Environment variables in `.envrc`
- `uv` package manager
- Python 3.13+
- Integration with other workspace projects

See `SKILL.md` for workspace-specific setup instructions.
