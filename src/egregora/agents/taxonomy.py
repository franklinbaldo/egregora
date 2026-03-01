"""Pydantic-AI agent for generating semantic taxonomy from content clusters."""
# TODO: [Taskmaster] Refactor brittle model name prefix stripping

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from egregora.llm.api_keys import get_google_api_key


class ClusterInput(BaseModel):
    """Input representation of a single cluster for the prompt."""

    cluster_id: int
    exemplars: list[str] = Field(description="Titles/Summaries of posts in this cluster")


class ClusterTags(BaseModel):
    """The tags assigned to a specific cluster."""

    cluster_id: int = Field(description="The ID of the cluster being labeled")
    tags: list[str] = Field(
        description="2-4 distinct tags that describe this specific topic group", min_length=2, max_length=4
    )


class GlobalTaxonomyResult(BaseModel):
    """The complete taxonomy map."""

    mappings: list[ClusterTags]


def create_global_taxonomy_agent(model_name: str) -> Agent[None, GlobalTaxonomyResult]:
    """Create the global taxonomy agent with fallback support."""
    provider = GoogleProvider(api_key=get_google_api_key())
    model = GoogleModel(
        model_name.removeprefix("google-gla:"),
        provider=provider,
    )

    system_prompt = """
    You are the Chief Taxonomist for a large technical archive.

    You have been given several groups (clusters) of blog posts.
    Your goal is to create a **consistent, non-overlapping taxonomy**.

    CRITICAL INSTRUCTIONS:
    1. **Contrast is Key**: Look at neighbor clusters. If Cluster 1 is "Python Basics" and Cluster 2 is "Python Async", do NOT tag both just "Python". Distinguish them.
    2. **Consistency**: Use the same granularity across clusters.
    3. **Tags**: Generate 2-4 tags per cluster. Mix broad (Category) and specific (Topic).
    4. **Output**: Return a strictly structured mapping of Cluster ID to Tag List.
    """

    return Agent(model=model, output_type=GlobalTaxonomyResult, system_prompt=system_prompt)
