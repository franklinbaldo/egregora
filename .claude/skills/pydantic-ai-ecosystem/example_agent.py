#!/usr/bin/env python3
"""
Example Pydantic AI agent with tools and structured output.
"""

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext


class CityInfo(BaseModel):
    """Structured output for city information."""
    name: str
    country: str
    population: int
    famous_for: list[str]


# Create agent with structured output
agent = Agent(
    'gemini-1.5-pro',  # or 'openai:gpt-4', 'anthropic:claude-sonnet-4-0'
    result_type=CityInfo,
    instructions='Extract structured city information from user queries.'
)


@agent.tool
async def search_population(ctx: RunContext, city: str) -> str:
    """Search for city population data."""
    # Mock implementation - replace with real API call
    populations = {
        'tokyo': 14_000_000,
        'paris': 2_200_000,
        'london': 9_000_000,
    }
    return f"Population of {city}: {populations.get(city.lower(), 'unknown'):,}"


async def main():
    """Run example agent queries."""
    result = await agent.run('Tell me about Tokyo')
    city: CityInfo = result.output

    print(f"\n{city.name}, {city.country}")
    print(f"Population: {city.population:,}")
    print(f"Famous for: {', '.join(city.famous_for)}")
    print(f"\nTokens used: {result.usage().total_tokens}")


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
