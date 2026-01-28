"""Module for generating a semantic taxonomy from content.

This module implements the logic for "Multi-Label Semantic Clustering". It works by:
1. Fetching document vectors from the RAG backend.
2. Clustering these vectors using K-Means to find semantic topics.
3. Sending the clusters to an LLM to generate a set of descriptive tags for each cluster.
4. Applying these generated tags to the corresponding documents.
"""

import logging
from typing import Any

import numpy as np

from egregora.agents.taxonomy import create_global_taxonomy_agent
from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.document import OutputSink
from egregora.rag import get_backend

logger = logging.getLogger(__name__)

# Conservative character limit for a "safe" context batch (approx 100k tokens ~ 400k chars)
# Gemini 1.5 has 1M+ context, but we keep it safe to avoid timeout/latency issues.
MAX_PROMPT_CHARS = 400_000


def generate_semantic_taxonomy(output_sink: OutputSink, config: EgregoraConfig) -> int:
    """Generates a semantic taxonomy from the content.

    Args:
        output_sink: The output sink to use for persisting documents.
        config: The Egregora configuration.

    Returns:
        The number of documents updated with new tags.

    """
    # Check if taxonomy is enabled
    if not config.taxonomy.enabled:
        logger.info("Taxonomy generation disabled via config")
        return 0

    try:
        from sklearn.cluster import KMeans  # type: ignore[import-untyped]
    except ModuleNotFoundError as exc:
        logger.warning("scikit-learn not installed (optional dependency). Skipping taxonomy: %s", exc)
        return 0
    except ImportError as exc:
        logger.warning("Failed to import scikit-learn dependencies. Skipping taxonomy: %s", exc)
        return 0

    backend = get_backend(db_dir=config.paths.lancedb_dir)

    # 1. Fetch & Cluster (Standard K-Means)
    if not hasattr(backend, "get_all_post_vectors"):
        logger.warning("RAG backend does not support vector retrieval. Skipping taxonomy.")
        return 0

    doc_ids, vectors = backend.get_all_post_vectors()
    n_docs = len(doc_ids)
    min_docs = config.taxonomy.min_docs
    if n_docs < min_docs:
        logger.info("Insufficient posts for clustering (<%d). Skipping taxonomy.", min_docs)
        return 0

    # Calculate k using configurable exponent or fixed value
    if config.taxonomy.num_clusters is not None:
        k = config.taxonomy.num_clusters
    else:
        # k = n^exponent (default exponent=0.5 gives sqrt(n))
        k = max(2, int(n_docs**config.taxonomy.cluster_exponent))

    logger.info(
        "Clustering %d posts into %d semantic topics (exponent=%.2f)...",
        n_docs,
        k,
        config.taxonomy.cluster_exponent,
    )

    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(vectors)

    # 2. Build Global Context
    all_docs = list(output_sink.documents())
    doc_lookup = {d.document_id: d for d in all_docs}

    raw_clusters: dict[int, list[str]] = _group_clusters(k, labels, doc_ids)
    clusters_input = _build_cluster_prompts(raw_clusters, doc_lookup)

    # 3. Batched Global Inference
    agent = create_global_taxonomy_agent(config.models.writer)
    batches = _create_batches(clusters_input)

    if len(batches) > 1:
        logger.info("Taxonomy input too large, split into %d batches.", len(batches))

    batch_results = _process_batches(agent, batches)

    # 4. Apply Updates
    # Flatten results
    all_mappings = [m for sublist in batch_results for m in sublist]
    return _apply_updates(output_sink, all_mappings, raw_clusters, doc_lookup)


def _group_clusters(k: int, labels: np.ndarray, doc_ids: list[str]) -> dict[int, list[str]]:
    raw_clusters: dict[int, list[str]] = {i: [] for i in range(k)}
    for idx, label in enumerate(labels):
        raw_clusters[label].append(doc_ids[idx])
    return raw_clusters


def _build_cluster_prompts(raw_clusters: dict[int, list[str]], doc_lookup: dict) -> list[str]:
    clusters_input = []
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
    return clusters_input


def _create_batches(clusters_input: list[str]) -> list[list[str]]:
    batches = []
    current_batch: list[str] = []
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
    return batches


def _process_batches(agent: Any, batches: list[list[str]]) -> list[Any]:
    batch_results = []
    for batch_items in batches:
        prompt = (
            "Analyze these document clusters and generate a distinct tag set for each.\n\n"
            + "\n\n".join(batch_items)
        )
        try:
            result = agent.run_sync(prompt)
            batch_results.append(result.output.mappings)
        except Exception as e:
            logger.warning("Batch taxonomy generation failed: %s", e)
            batch_results.append([])
    return batch_results


def _apply_updates(
    output_sink: OutputSink,
    all_mappings: list[Any],
    raw_clusters: dict[int, list[str]],
    doc_lookup: dict,
) -> int:
    updates_count = 0
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
