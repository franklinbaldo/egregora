(function() {
    const CONFIG = {
        // Path relative to site root. Material theme handles base_url via 'url' filter in template
        indexPath: "assets/data/related.json",
        containerId: "related-posts-container"
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
                    return {};
                });
        }
        return indexPromise;
    }

    async function initRelatedPosts() {
        const container = document.getElementById(CONFIG.containerId);
        if (!container) return; // Not a post page or container missing

        // 1. Determine current URL from data attribute
        const article = container.closest("article");
        let currentCanonicalUrl = article ? article.getAttribute("data-url") : null;

        if (!currentCanonicalUrl) return;

        // Normalize URL: remove leading slash to match Python generation
        if (currentCanonicalUrl.startsWith("/")) {
            currentCanonicalUrl = currentCanonicalUrl.substring(1);
        }

        // 2. Resolve base path for fetching assets
        const basePath = document.querySelector('base') ? document.querySelector('base').href : "./";

        // 3. Fetch Index
        const index = await getIndex(basePath);
        if (!index) return;

        // 4. Lookup Related Posts
        // We try exact match first
        let relatedPosts = index[currentCanonicalUrl];

        // If not found, try robust matching (e.g. handling index.html vs root)
        if (!relatedPosts) {
             // If URL ends in /, try adding index.html, or vice versa if needed
             // But for now, we assume the python generator produces canonical URLs consistent with this
             // Let's try matching purely on the end if simple lookup fails
             const keys = Object.keys(index);
             const match = keys.find(k => k === currentCanonicalUrl || currentCanonicalUrl.endsWith(k) || k.endsWith(currentCanonicalUrl));
             if (match) {
                 relatedPosts = index[match];
             }
        }

        if (!relatedPosts || relatedPosts.length === 0) return;

        // 5. Render
        const listHtml = relatedPosts.map(post => `
            <a href="${basePath}${post.u}" class="related-card">
                <div class="related-title">${post.t}</div>
                <div class="related-meta">
                    <span>${post.d}</span>
                    ${post.score ? `<span class="related-score" title="Semantic Match">${Math.round(post.score * 100)}% match</span>` : ''}
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
    if (window.document$) {
        window.document$.subscribe(() => {
            setTimeout(initRelatedPosts, 100);
        });
    } else {
        document.addEventListener("DOMContentLoaded", initRelatedPosts);
    }
})();
