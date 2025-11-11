#!/usr/bin/env python3
"""Example Pydantic Graph workflow with state management."""

from dataclasses import dataclass, field

from pydantic_graph import BaseNode, End, Graph, GraphRunContext


@dataclass
class WorkflowState:
    """State that persists across graph nodes."""

    user_input: str
    processing_steps: list[str] = field(default_factory=list)
    result: str = ""


@dataclass
class ValidateInput(BaseNode):
    """Validate user input."""

    async def run(self, ctx: GraphRunContext[WorkflowState]) -> 'ProcessData | InvalidInput':
        ctx.state.processing_steps.append("Validating input")

        if len(ctx.state.user_input) > 0:
            return ProcessData()
        return InvalidInput()


@dataclass
class ProcessData(BaseNode):
    """Process validated data."""

    async def run(self, ctx: GraphRunContext[WorkflowState]) -> 'GenerateOutput':
        ctx.state.processing_steps.append("Processing data")
        # Simulate processing
        ctx.state.result = f"Processed: {ctx.state.user_input.upper()}"
        return GenerateOutput()


@dataclass
class GenerateOutput(BaseNode):
    """Generate final output."""

    async def run(self, ctx: GraphRunContext[WorkflowState]) -> End:
        ctx.state.processing_steps.append("Generating output")
        ctx.state.result += " [COMPLETE]"
        return End()


@dataclass
class InvalidInput(BaseNode):
    """Handle invalid input."""

    async def run(self, ctx: GraphRunContext[WorkflowState]) -> End:
        ctx.state.processing_steps.append("Invalid input detected")
        ctx.state.result = "ERROR: Empty input"
        return End()


async def main() -> None:
    """Run example graph workflow."""
    # Create graph
    graph = Graph(nodes=[ValidateInput, ProcessData, GenerateOutput, InvalidInput])

    # Generate and print Mermaid diagram

    # Test with valid input
    state1 = WorkflowState(user_input="hello world")
    await graph.run(ValidateInput(), state=state1)


    # Test with invalid input
    state2 = WorkflowState(user_input="")
    await graph.run(ValidateInput(), state=state2)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
