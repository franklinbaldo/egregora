"""Prototype script for 'The Living Grimoire' (Project Alexandria).

This script simulates the 'Concept Miner' pipeline:
1.  Ingest Mock Entries (Chat Logs).
2.  Extract Concepts (using a mock or real LLM).
3.  Synthesize a Wiki Page.

Usage:
    uv run python scripts/prototype_grimoire.py
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Ensure src is in path
sys.path.append("src")

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel

from egregora_v3.core.types import Document, DocumentType, DocumentStatus
from egregora_v3.knowledge.concepts import WikiPage, ConceptType, ConceptExtraction
from egregora.utils.model_fallback import create_fallback_model

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("grimoire")


# --- Mock Data ---

MOCK_CHATS = [
    Document.create(
        content="Gary: Do you remember the Noodle Incident of 2018? It was wild.",
        doc_type=DocumentType.POST,
        title="Chat Log 2024-01-01",
        id_override="msg-001"
    ),
    Document.create(
        content="Alice: Yeah, the camping trip where Gary lost the noodles in the river.",
        doc_type=DocumentType.POST,
        title="Chat Log 2024-01-01",
        id_override="msg-002"
    ),
    Document.create(
        content="Bob: Classic Gary move. Just like when he lost the tent poles in 2019.",
        doc_type=DocumentType.POST,
        title="Chat Log 2024-01-02",
        id_override="msg-003"
    ),
]


# --- Agent Definitions ---

class ConceptExtractionResult(BaseModel):
    concepts: list[ConceptExtraction]


def create_extractor_agent() -> Agent[None, ConceptExtractionResult] | None:
    """Agent to extract concepts from raw text."""
    try:
        # Use a cheap model for prototype
        model = create_fallback_model("google-gla:gemini-1.5-flash")

        return Agent(
            model=model,
            result_type=ConceptExtractionResult,
            system_prompt=(
                "You are a Concept Miner. Read the chat logs and extract distinct concepts "
                "(People, Events, Places, Memes). Ignore trivial chatter."
            )
        )
    except ValueError:
        return None


class WikiSynthesizerResult(BaseModel):
    markdown_content: str
    aliases: list[str]
    relations: list[str] # Simplified for prototype


def create_synthesizer_agent() -> Agent[None, WikiSynthesizerResult] | None:
    """Agent to write the wiki page."""
    try:
        model = create_fallback_model("google-gla:gemini-1.5-flash")

        return Agent(
            model=model,
            result_type=WikiSynthesizerResult,
            system_prompt=(
                "You are the Group Historian. Synthesize the provided snippets into a "
                "comprehensive Wiki Page for the concept. Use a neutral, encyclopedic tone."
            )
        )
    except ValueError:
        return None


# --- Pipeline ---

async def run_concept_mining():
    logger.info("🔮 Starting Grimoire Prototype...")

    # 1. Extraction Phase
    extractor = create_extractor_agent()
    all_extractions = []

    logger.info(f"📚 Processing {len(MOCK_CHATS)} mock entries...")

    for doc in MOCK_CHATS:
        # Real pipeline would check if doc is relevant
        try:
            # Check for API key / Agent
            if not extractor:
                logger.warning("⚠️ No API Key found. Skipping actual LLM call.")
                # Return mock result
                result = ConceptExtractionResult(concepts=[
                    ConceptExtraction(name="The Noodle Incident", type=ConceptType.EVENT, description="Event where noodles were lost."),
                    ConceptExtraction(name="Gary", type=ConceptType.PERSON, description="A chaotic group member.")
                ])
            else:
                result_run = await extractor.run(doc.content)
                result = result_run.data

            all_extractions.extend(result.concepts)
            logger.info(f"   -> Extracted {len(result.concepts)} concepts from {doc.id}")

        except Exception as e:
            logger.error(f"❌ Extraction failed: {e}")

    # 2. Clustering (Mocked)
    # Group by name
    clusters = {}
    for c in all_extractions:
        key = c.name.lower() # Naive normalization
        if key not in clusters:
            clusters[key] = []
        clusters[key].append(c)

    logger.info(f"🧩 Found {len(clusters)} unique concept clusters.")

    # 3. Synthesis Phase
    synthesizer = create_synthesizer_agent()

    for key, concepts in clusters.items():
        concept_name = concepts[0].name
        concept_type = concepts[0].type

        logger.info(f"✍️ Synthesizing Wiki Page for: {concept_name} ({concept_type})")

        context_str = "\n".join([f"- {c.description}" for c in concepts])
        prompt = f"Write a wiki page for '{concept_name}' based on these notes:\n{context_str}"

        try:
             if not synthesizer:
                 content = f"# {concept_name}\n\nThis is a mock wiki page synthesized from {len(concepts)} mentions."
                 aliases = ["Mock Alias"]
             else:
                result_run = await synthesizer.run(prompt)
                content = result_run.data.markdown_content
                aliases = result_run.data.aliases

             # Create the WikiPage Artifact
             page = WikiPage.create_concept(
                 name=concept_name,
                 content=content,
                 concept_type=concept_type,
                 evidence_refs=["mock-refs"],
                 aliases=aliases
             )

             logger.info("✨ GENERATED ARTIFACT:")
             logger.info("-" * 40)
             logger.info(f"ID: {page.id}")
             logger.info(f"Slug: {page.slug}")
             logger.info("-" * 40)
             logger.info(page.content)
             logger.info("-" * 40)

        except Exception as e:
            logger.error(f"❌ Synthesis failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_concept_mining())
