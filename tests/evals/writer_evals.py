"""Writer agent evaluation dataset.

This module defines test cases for evaluating the writer agent's ability to:
- Decide when to write posts (0-N posts per period)
- Generate appropriate metadata (titles, tags, dates)
- Use RAG context appropriately
- Maintain quality standards
"""

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance


def create_writer_dataset() -> Dataset:
    """Create evaluation dataset for writer agent.

    Returns:
        Dataset with test cases for writer evaluation
    """
    cases = [
        Case(
            name="empty_conversation",
            inputs={
                "prompt": "You reviewed an empty conversation. No messages to analyze.",
                "period_date": "2025-01-01",
            },
            expected_output={"posts_created": 0, "summary": "No content to write about"},
            metadata={"category": "edge_case", "difficulty": "easy"},
        ),
        Case(
            name="single_message_insufficient",
            inputs={
                "prompt": (
                    "Conversation (2025-01-01):\n- user_abc: hi\n\nThis is too brief to warrant a blog post."
                ),
                "period_date": "2025-01-01",
            },
            expected_output={"posts_created": 0, "summary": "Insufficient content"},
            metadata={"category": "edge_case", "difficulty": "easy"},
        ),
        Case(
            name="single_topic_discussion",
            inputs={
                "prompt": (
                    "Conversation (2025-01-15):\n"
                    "Discussion about quantum computing basics, multiple participants "
                    "sharing insights about qubits, superposition, and entanglement. "
                    "Rich technical discussion with examples.\n\n"
                    "Write 0-N blog posts based on this conversation."
                ),
                "period_date": "2025-01-15",
            },
            expected_output={
                "posts_created": 1,
                "has_title": True,
                "has_tags": True,
                "topic_match": "quantum computing",
            },
            metadata={"category": "single_topic", "difficulty": "medium"},
        ),
        Case(
            name="multi_topic_discussion",
            inputs={
                "prompt": (
                    "Conversation (2025-02-01):\n"
                    "1. Discussion about AI ethics and safety (10 messages)\n"
                    "2. Debate about climate change solutions (12 messages)\n"
                    "3. Book recommendations for sci-fi (8 messages)\n\n"
                    "Each topic has substantial content. Write 0-N posts."
                ),
                "period_date": "2025-02-01",
            },
            expected_output={
                "posts_created": 3,
                "topics_covered": ["AI ethics", "climate change", "sci-fi books"],
            },
            metadata={"category": "multi_topic", "difficulty": "hard"},
        ),
        Case(
            name="with_rag_context",
            inputs={
                "prompt": (
                    "Conversation (2025-03-01):\n"
                    "Follow-up discussion on machine learning continues from last week. "
                    "Participants reference previous posts about neural networks.\n\n"
                    "## Related Previous Posts:\n"
                    "### [Introduction to Neural Networks] (2025-02-20)\n"
                    "Basic overview of neural network architecture...\n\n"
                    "Write posts that reference relevant previous content."
                ),
                "period_date": "2025-03-01",
            },
            expected_output={
                "posts_created": 1,
                "references_previous_posts": True,
            },
            metadata={"category": "rag_usage", "difficulty": "hard"},
        ),
    ]

    evaluators = [
        IsInstance(type_name="dict"),
        # Note: LLM judges will be added once we establish baseline scores
    ]

    return Dataset(cases=cases, evaluators=evaluators)


def create_writer_quality_dataset_with_judges() -> Dataset:
    """Create writer evaluation dataset with LLM judges.

    This version includes LLM judges for semantic evaluation.
    Only use when ready for live evaluation with API key.

    Returns:
        Dataset with test cases and LLM judges
    """
    from pydantic_evals.evaluators import LLMJudge

    cases = create_writer_dataset().cases

    # LLM judge for post quality
    quality_judge = LLMJudge(
        model="gemini-1.5-flash",
        prompt="""Evaluate the writer agent's output quality.

Consider:
1. Decision making: Did it appropriately decide how many posts to generate (0-N)?
2. Metadata quality: Are titles clear, tags relevant, dates correct?
3. Content appropriateness: Does content match the conversation topics?
4. RAG usage: If context was provided, was it used appropriately?

Score 0.0-1.0 where:
- 0.0-0.3: Poor (wrong decisions, missing metadata, irrelevant content)
- 0.4-0.6: Fair (some issues but generally acceptable)
- 0.7-0.8: Good (minor issues only)
- 0.9-1.0: Excellent (perfect execution)

Return ONLY a JSON object with "score" (0.0-1.0) and "reason" (brief explanation).
""",
    )

    # LLM judge for RAG integration
    rag_judge = LLMJudge(
        model="gemini-1.5-flash",
        prompt="""Evaluate how well the agent used RAG context.

If "Related Previous Posts" were provided in the prompt:
- Did the agent reference or link to previous posts when relevant?
- Did it maintain conversation continuity?
- Did it avoid contradicting previous content?

If NO RAG context was provided:
- Score should be 1.0 (N/A)

Score 0.0-1.0 where:
- 0.0-0.3: Ignored context or contradicted it
- 0.4-0.6: Minimal use of context
- 0.7-0.8: Good use of context
- 0.9-1.0: Excellent integration or N/A

Return ONLY a JSON object with "score" (0.0-1.0) and "reason" (brief explanation).
""",
    )

    return Dataset(
        cases=cases,
        evaluators=[
            IsInstance(type_name="dict"),
            quality_judge,
            rag_judge,
        ],
    )
