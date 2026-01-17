"""Pydantic models for structured persona extraction."""

from pydantic import BaseModel, Field


class PersonaModel(BaseModel):
    """Structured representation of a user's communication persona.

    This model captures the "voice" and "mindset" of a user, used for
    simulating their behavior in the Egregora Simulator.
    """

    communication_style: str = Field(
        description="Description of how the user communicates (e.g., 'Formal and detailed', 'Terse and emoji-heavy')."
    )
    core_values: list[str] = Field(
        description="List of 3-5 core values or priorities inferred from arguments (e.g., 'Performance', 'Code Quality').",
        min_length=1,
        max_length=5,
    )
    argumentation_style: str = Field(
        description="How the user argues (e.g., 'Socratic', 'Data-driven', 'Devil's Advocate', 'Consensus-builder')."
    )
    frequent_topics: list[str] = Field(
        description="List of 3-5 topics the user discusses most frequently.",
        min_length=1,
        max_length=10,
    )
    voice_sample: str = Field(
        description="A short, synthetic sentence that captures the user's typical tone and style."
    )
