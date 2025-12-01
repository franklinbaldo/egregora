import asyncio
import logging

import numpy as np
from sklearn.cluster import KMeans

from egregora.agents.taxonomy import create_global_taxonomy_agent
from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.protocols import OutputSink
from egregora.rag import get_backend

logger = logging.getLogger(__name__)

# Conservative character limit for a "safe" context batch (approx 100k tokens ~ 400k chars)
# Gemini 1.5 has 1M+ context, but we keep it safe to avoid timeout/latency issues.
MAX_PROMPT_CHARS = 400_000


async def generate_semantic_taxonomy(output_sink: OutputSink, config: EgregoraConfig) -> int:
    backend = get_backend()

    # 1. Fetch & Cluster (Standard K-Means)
    if not hasattr(backend, "get_all_post_vectors"):
        logger.warning("RAG backend does not support vector retrieval. Skipping taxonomy.")
        return 0

    doc_ids, X = await backend.get_all_post_vectors()
    n_docs = len(doc_ids)
    if n_docs < 5:
        logger.info("Insufficient posts for clustering (<5). Skipping taxonomy.")
        return 0

    k = max(2, int(np.sqrt(n_docs / 2)))
    logger.info("Clustering %d posts into %d semantic topics...", n_docs, k)

    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)

    # 2. Build Global Context
    all_docs = list(output_sink.documents())
    doc_lookup = {d.document_id: d for d in all_docs}

    clusters_input = []

    # Group IDs first
    raw_clusters = {i: [] for i in range(k)}
    for idx, label in enumerate(labels):
        raw_clusters[label].append(doc_ids[idx])

    # Build Prompt Data
    for cid, member_ids in raw_clusters.items():
        exemplars = []
        # Take top 5 to represent the cluster
        for doc_id in member_ids[:5]:
            doc = doc_lookup.get(doc_id)
            if doc:
                meta = doc.metadata
                exemplars.append(f"{meta.get('title', 'Untitled')}: {meta.get('summary', '')[:100]}...")

        if exemplars:
            clusters_input.append(f"Cluster {cid}:\n" + "\n".join(f"- {ex}" for ex in exemplars))

    # 3. Batched Global Inference
    agent = create_global_taxonomy_agent(config.models.writer)

    # Simple batching by character count
    batches = []
    current_batch = []
    current_chars = 0

    for item in clusters_input:
        item_len = len(item)
        if current_chars + item_len > MAX_PROMPT_CHARS:
            batches.append(current_batch)
            current_batch = [item]
            current_chars = item_len
        else:
            current_batch.append(item)
            current_chars += item_len
    if current_batch:
        batches.append(current_batch)

    if len(batches) > 1:
        logger.info("Taxonomy input too large, split into %d batches.", len(batches))

    updates_count = 0

    # Process batches concurrently
    async def process_batch(batch_items):
        prompt = (
            "Analyze these document clusters and generate a distinct tag set for each.\n\n"
            + "\n\n".join(batch_items)
        )
        try:
            result = await agent.run(prompt)
            return result.data.mappings
        except Exception as e:
            logger.warning("Batch taxonomy generation failed: %s", e)
            return []

    # Run all batches
    batch_results = await asyncio.gather(*[process_batch(b) for b in batches])

    # Flatten results
    all_mappings = [m for sublist in batch_results for m in sublist]

    # 4. Apply Updates
    for mapping in all_mappings:
        cid = mapping.cluster_id
        new_tags = mapping.tags

        member_ids = raw_clusters.get(cid, [])
        logger.info("Cluster %d -> %s (%d posts)", cid, new_tags, len(member_ids))

        for doc_id in member_ids:
            doc = doc_lookup.get(doc_id)
            if not doc:
                continue

            # Idempotent merge
            current_tags = set(doc.metadata.get("tags", []))
            original_lower = {t.lower() for t in current_tags}

            modified = False
            for tag in new_tags:
                if tag.lower() not in original_lower:
                    current_tags.add(tag)
                    modified = True

            if modified:
                updated = doc.with_metadata(tags=list(current_tags))
                output_sink.persist(updated)
                updates_count += 1

    return updates_count
