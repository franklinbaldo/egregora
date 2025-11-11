#!/usr/bin/env python3
"""Example fasta2a (Agent-to-Agent protocol) usage.

This demonstrates exposing a Pydantic AI agent as an A2A server
for agent-to-agent communication.

Run with: uvicorn example_fasta2a:app --reload
"""

from pydantic_ai import Agent, RunContext

# Create agent with tools
agent = Agent(
    'gemini-1.5-pro',
    instructions='Be helpful and concise. Use tools when appropriate.'
)


@agent.tool
async def get_weather(ctx: RunContext, city: str) -> str:
    """Get weather information for a city."""
    # Mock implementation
    return f"The weather in {city} is sunny and 72°F"


@agent.tool
async def search_web(ctx: RunContext, query: str) -> str:
    """Search the web for information."""
    # Mock implementation
    return f"Found information about: {query}"


# Convert agent to A2A server (returns FastAPI app)
app = agent.to_a2a()


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
