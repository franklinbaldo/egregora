import logging

import numpy as np
from sklearn.cluster import KMeans

from egregora.agents.taxonomy import create_global_taxonomy_agent
from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.protocols import OutputSink
from egregora.rag import get_backend

logger = logging.getLogger(__name__)


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

    # 3. Single Global Inference
    # We join all clusters into one giant prompt so the LLM sees the boundaries
    agent = create_global_taxonomy_agent(config.models.writer)

    prompt = "Analyze these document clusters and generate a distinct tag set for each.\n\n" + "\n\n".join(
        clusters_input
    )

    logger.info("Generating global taxonomy map...")
    try:
        result = await agent.run(prompt)
        taxonomy_map = result.data.mappings  # List[ClusterTags]
    except Exception as e:
        logger.warning("Taxonomy generation failed: %s", e)
        return 0

    # 4. Apply Updates
    updates_count = 0

    for mapping in taxonomy_map:
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
