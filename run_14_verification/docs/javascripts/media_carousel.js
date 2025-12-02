// Media Carousel with Smart Embeds and Filtering

class MediaCarousel {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.currentIndex = 0;
        this.mediaItems = [];
        this.filteredItems = [];

        this.init();
    }

    async init() {
        await this.fetchMediaItems();
        this.render();
        this.setupFilters();
        this.setupKeyboard();
    }

    async fetchMediaItems() {
        // Fetch all media from docs/media/urls/*.md
        // For now, using hardcoded data - will be replaced with actual fetch
        this.mediaItems = window.MEDIA_DATA || [];
        this.filteredItems = [...this.mediaItems];
    }

    detectEmbedType(url) {
        if (url.includes('youtube.com') || url.includes('youtu.be')) return 'youtube';
        if (url.includes('vimeo.com')) return 'vimeo';
        if (url.includes('twitter.com') || url.includes('x.com')) return 'twitter';
        if (url.includes('spotify.com')) return 'spotify';
        if (url.includes('github.com')) return 'github';
        return 'card';
    }

    getYouTubeId(url) {
        const match = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\s]+)/);
        return match ? match[1] : null;
    }

    getVimeoId(url) {
        const match = url.match(/vimeo\.com\/(\d+)/);
        return match ? match[1] : null;
    }

    renderEmbed(item) {
        const type = this.detectEmbedType(item.url);

        switch (type) {
            case 'youtube':
                const ytId = this.getYouTubeId(item.url);
                return `
          <div class="media-embed">
            <iframe src="https://www.youtube.com/embed/${ytId}"
              allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture"
              allowfullscreen></iframe>
          </div>
          <h3>${item.title}</h3>
          <p>${item.summary}</p>
        `;

            case 'vimeo':
                const vimeoId = this.getVimeoId(item.url);
                return `
          <div class="media-embed">
            <iframe src="https://player.vimeo.com/video/${vimeoId}"
              allow="autoplay; fullscreen" allowfullscreen></iframe>
          </div>
          <h3>${item.title}</h3>
          <p>${item.summary}</p>
        `;

            case 'spotify':
                return this.renderCard(item, '🎵');

            default:
                return this.renderCard(item, '🔗');
        }
    }

    renderCard(item, icon = '🔗') {
        const domain = new URL(item.url).hostname.replace('www.', '');
        const tags = item.tags ? item.tags.map(tag =>
            `<span class="media-tag">${tag}</span>`
        ).join('') : '';

        return `
      <div class="media-card">
        <div class="media-card-icon">${icon}</div>
        <h3>${item.title}</h3>
        <p>${item.summary}</p>
        <a href="${item.url}" target="_blank" rel="noopener" class="media-card-link">
          Open link →
        </a>
        <div class="media-meta">
          <span>${domain}</span>
          ${item.date ? `<span>${new Date(item.date).toLocaleDateString()}</span>` : ''}
        </div>
        ${tags ? `<div class="media-tags">${tags}</div>` : ''}
      </div>
    `;
    }

    render() {
        if (this.filteredItems.length === 0) {
            this.container.innerHTML = '<p style="text-align:center;padding:2rem;">No media items found</p>';
            return;
        }

        const slides = this.filteredItems.map(item => `
      <div class="media-slide">
        ${this.renderEmbed(item)}
      </div>
    `).join('');

        const dots = this.filteredItems.map((_, i) =>
            `<div class="carousel-dot ${i === 0 ? 'active' : ''}" data-index="${i}"></div>`
        ).join('');

        this.container.innerHTML = `
      <div class="media-carousel">
        <div class="media-slides">${slides}</div>
      </div>
      <div class="carousel-controls">
        <button class="carousel-button" id="prev-btn">←</button>
        <div class="carousel-dots">${dots}</div>
        <button class="carousel-button" id="next-btn">→</button>
      </div>
      <div class="media-count">
        ${this.currentIndex + 1} / ${this.filteredItems.length}
      </div>
    `;

        this.setupControls();
    }

    setupControls() {
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');
        const dots = document.querySelectorAll('.carousel-dot');

        prevBtn?.addEventListener('click', () => this.prev());
        nextBtn?.addEventListener('click', () => this.next());

        dots.forEach(dot => {
            dot.addEventListener('click', (e) => {
                this.goTo(parseInt(e.target.dataset.index));
            });
        });

        this.updateControls();
    }

    setupFilters() {
        const typeFilter = document.getElementById('media-type-filter');
        const tagFilter = document.getElementById('media-tag-filter');
        const searchInput = document.getElementById('media-search');

        typeFilter?.addEventListener('change', () => this.applyFilters());
        tagFilter?.addEventListener('change', () => this.applyFilters());
        searchInput?.addEventListener('input', () => this.applyFilters());
    }

    applyFilters() {
        const type = document.getElementById('media-type-filter')?.value || 'all';
        const tag = document.getElementById('media-tag-filter')?.value || 'all';
        const search = document.getElementById('media-search')?.value.toLowerCase() || '';

        this.filteredItems = this.mediaItems.filter(item => {
            const matchesType = type === 'all' || this.detectEmbedType(item.url) === type;
            const matchesTag = tag === 'all' || (item.tags && item.tags.includes(tag));
            const matchesSearch = !search ||
                item.title.toLowerCase().includes(search) ||
                item.summary.toLowerCase().includes(search);

            return matchesType && matchesTag && matchesSearch;
        });

        this.currentIndex = 0;
        this.render();
    }

    setupKeyboard() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') this.prev();
            if (e.key === 'ArrowRight') this.next();
        });
    }

    goTo(index) {
        this.currentIndex = Math.max(0, Math.min(index, this.filteredItems.length - 1));
        const slides = document.querySelector('.media-slides');
        if (slides) {
            slides.style.transform = `translateX(-${this.currentIndex * 100}%)`;
        }
        this.updateControls();
    }

    next() {
        if (this.currentIndex < this.filteredItems.length - 1) {
            this.goTo(this.currentIndex + 1);
        }
    }

    prev() {
        if (this.currentIndex > 0) {
            this.goTo(this.currentIndex - 1);
        }
    }

    updateControls() {
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');
        const dots = document.querySelectorAll('.carousel-dot');
        const count = document.querySelector('.media-count');

        if (prevBtn) prevBtn.disabled = this.currentIndex === 0;
        if (nextBtn) nextBtn.disabled = this.currentIndex === this.filteredItems.length - 1;

        dots.forEach((dot, i) => {
            dot.classList.toggle('active', i === this.currentIndex);
        });

        if (count) {
            count.textContent = `${this.currentIndex + 1} / ${this.filteredItems.length}`;
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('media-carousel-root')) {
        new MediaCarousel('media-carousel-root');
    }
});
