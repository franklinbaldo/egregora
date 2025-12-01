(function() {
    const CONFIG = {
        // Path relative to site root. Material theme handles base_url via 'url' filter in template
        indexPath: "assets/data/search.json",
        containerId: "related-posts-container",
        maxResults: 3,
        threshold: 0.3 // Minimum similarity score
    };

    // Cache the index promise to avoid refetching on navigation
    let indexPromise = null;

    function getIndex(basePath) {
        if (!indexPromise) {
            indexPromise = fetch(basePath + CONFIG.indexPath)
                .then(response => {
                    if (!response.ok) throw new Error("Index not found");
                    return response.json();
                })
                .catch(err => {
                    console.warn("Egregora related posts disabled:", err);
                    return [];
                });
        }
        return indexPromise;
    }

    function cosineSimilarity(vecA, vecB) {
        if (!vecA || !vecB || vecA.length !== vecB.length) return 0;
        let dot = 0, normA = 0, normB = 0;
        for (let i = 0; i < vecA.length; i++) {
            dot += vecA[i] * vecB[i];
            normA += vecA[i] * vecA[i];
            normB += vecB[i] * vecB[i];
        }
        return dot / (Math.sqrt(normA) * Math.sqrt(normB));
    }

    async function initRelatedPosts() {
        const container = document.getElementById(CONFIG.containerId);
        if (!container) return; // Not a post page or container missing

        // 1. Determine current URL from data attribute (robust against trailing slashes)
        // The container usually sits inside <article>
        const article = container.closest("article");
        const currentCanonicalUrl = article ? article.getAttribute("data-url") : null;

        if (!currentCanonicalUrl) return;

        // 2. Resolve base path for fetching assets
        // MkDocs Material provides 'base_url' in global config usually, or we infer relative
        const basePath = document.querySelector('base') ? document.querySelector('base').href : "./";

        // 3. Fetch & Search
        const index = await getIndex(basePath);
        if (!index || index.length === 0) return;

        // Find current post vector
        // We match loosely on the end of the URL to handle dev vs prod paths
        const currentPost = index.find(p => currentCanonicalUrl.endsWith(p.u) || p.u.endsWith(currentCanonicalUrl));

        if (!currentPost || !currentPost.v) return;

        // Compute scores
        const candidates = index
            .filter(p => p !== currentPost)
            .map(p => ({
                item: p,
                score: cosineSimilarity(currentPost.v, p.v)
            }))
            .filter(c => c.score > CONFIG.threshold)
            .sort((a, b) => b.score - a.score)
            .slice(0, CONFIG.maxResults);

        if (candidates.length === 0) return;

        // 4. Render
        const listHtml = candidates.map(c => `
            <a href="${basePath}${c.item.u}" class="related-card">
                <div class="related-title">${c.item.t}</div>
                <div class="related-meta">
                    <span>${c.item.d}</span>
                    <span class="related-score" title="Semantic Match">${Math.round(c.score * 100)}% match</span>
                </div>
            </a>
        `).join("");

        container.innerHTML = `
            <h2>Running Threads</h2>
            <p class="related-intro">Other posts exploring similar concepts:</p>
            <div class="related-grid">${listHtml}</div>
        `;
        container.classList.add("loaded");
    }

    // Hook into MkDocs Material navigation
    // document$ is an RxJS observable present in Material for MkDocs
    if (window.document$) {
        window.document$.subscribe(() => {
            // Short timeout to ensure DOM is ready after transition
            setTimeout(initRelatedPosts, 100);
        });
    } else {
        document.addEventListener("DOMContentLoaded", initRelatedPosts);
    }
})();
