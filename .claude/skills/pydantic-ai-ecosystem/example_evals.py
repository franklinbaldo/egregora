#!/usr/bin/env python3
"""Example Pydantic Evals usage for testing AI agents."""

from pydantic_ai import Agent
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance, LLMJudge

# Create agent to evaluate
agent = Agent(
    'gemini-1.5-pro',
    instructions='Answer geography questions concisely and accurately.'
)


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
    Case(
        name='largest_ocean',
        inputs='What is the largest ocean on Earth?',
        expected_output='Pacific Ocean'
    ),
]


# Create dataset with evaluators
dataset = Dataset(
    cases=cases,
    evaluators=[
        IsInstance(type_name='str'),
        LLMJudge(
            model='openai:gpt-4',
            prompt='Does the answer correctly match the expected output? Consider semantic equivalence.'
        )
    ]
)


async def run_agent(question: str) -> str:
    """Wrapper to run agent and return output."""
    result = await agent.run(question)
    return result.output


async def main() -> None:
    """Run evaluation and print results."""
    report = await dataset.evaluate(run_agent)

    report.print()



if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
