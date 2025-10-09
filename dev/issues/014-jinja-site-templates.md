# Issue #014: Jinja Templates for Generated Site Separation

## Priority: Medium
## Effort: Medium
## Type: Enhancement

## Problem Description

Currently, there's confusion between site generation templates and project documentation. The generated site (posts, reports) is mixed with technical documentation, making it difficult to:

1. **Separate Concerns**: Site content vs documentation vs system code
2. **Customize Output**: Limited control over generated site appearance
3. **Theme Management**: No consistent theming system for generated content
4. **Multi-Site Support**: Hard to generate different styles for different groups
5. **Maintenance**: Changes to site layout require code modifications

**Current limitations:**
- Site generation hardcoded in Python
- No template inheritance or theming
- Mixed documentation and site content
- Limited customization options

## Current Behavior

### Hardcoded Generation
```python
# src/egregora/generator.py - HTML generation hardcoded
def generate_html_post(self, post_data):
    return f"""
    <html>
        <head><title>{post_data.title}</title></head>
        <body>{post_data.content}</body>
    </html>
    """  # No templating system
```

### Mixed Content Structure
```
docs/
├── index.md              # Site homepage (generated content)
├── developer-guide/      # Technical documentation  
├── user-guide/           # System documentation
└── posts/                # Generated posts
    ├── daily/
    └── weekly/
```

## Proposed Solution

### 1. Jinja2 Template System

```python
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

class SiteTemplateEngine:
    """Jinja2-based template engine for generated sites."""
    
    def __init__(self, template_dir: Path, theme: str = "default"):
        self.template_dir = template_dir
        self.theme = theme
        self.env = Environment(
            loader=FileSystemLoader([
                template_dir / "themes" / theme,
                template_dir / "shared"
            ]),
            autoescape=True
        )
        
        # Register custom filters
        self.env.filters['format_date'] = self.format_date
        self.env.filters['anonymize'] = self.anonymize_content
        self.env.filters['markdown'] = self.render_markdown
    
    def render_template(self, template_name: str, **context) -> str:
        """Render template with context."""
        template = self.env.get_template(template_name)
        return template.render(**context)
```

### 2. Template Directory Structure

```
templates/
├── themes/
│   ├── default/           # Default theme
│   │   ├── base.html      # Base layout
│   │   ├── daily.html     # Daily post template
│   │   ├── weekly.html    # Weekly summary
│   │   ├── index.html     # Site homepage
│   │   └── assets/
│   │       ├── css/
│   │       ├── js/
│   │       └── images/
│   ├── minimal/           # Minimal theme
│   │   ├── base.html
│   │   ├── daily.html
│   │   └── assets/
│   └── corporate/         # Corporate theme
├── shared/                # Shared templates
│   ├── macros.html        # Reusable macros
│   ├── filters.html       # Custom filters
│   └── components/
│       ├── navigation.html
│       ├── post-meta.html
│       └── media-embed.html
└── email/                 # Email templates
    ├── daily-digest.html
    └── weekly-summary.html
```

### 3. Base Template System

```html
<!-- templates/themes/default/base.html -->
<!DOCTYPE html>
<html lang="{{ site.language }}" data-theme="{{ site.theme }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}{{ site.title }}{% endblock %}</title>
    
    <!-- Theme CSS -->
    <link rel="stylesheet" href="{{ url_for('assets', filename='css/theme.css') }}">
    <link rel="stylesheet" href="{{ url_for('assets', filename='css/components.css') }}">
    
    <!-- Feed links -->
    <link rel="alternate" type="application/rss+xml" 
          title="{{ site.title }} - Daily" 
          href="{{ url_for('feeds/daily.xml') }}">
    
    {% block head %}{% endblock %}
</head>
<body>
    <header class="site-header">
        {% include 'components/navigation.html' %}
    </header>

    <main class="site-main">
        {% block content %}{% endblock %}
    </main>

    <footer class="site-footer">
        {% include 'components/footer.html' %}
    </footer>

    <script src="{{ url_for('assets', filename='js/theme.js') }}"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

### 4. Daily Post Template

```html
<!-- templates/themes/default/daily.html -->
{% extends "base.html" %}

{% block title %}{{ post.group_name }} - {{ post.date | format_date }}{% endblock %}

{% block content %}
<article class="daily-post">
    <header class="post-header">
        <h1>{{ post.group_name }}</h1>
        <time datetime="{{ post.date.isoformat() }}" class="post-date">
            {{ post.date | format_date('full') }}
        </time>
        
        <div class="post-meta">
            <span class="message-count">{{ post.message_count }} mensagens</span>
            <span class="participant-count">{{ post.participants | length }} participantes</span>
            {% if post.topics %}
            <div class="topics">
                {% for topic in post.topics %}
                <span class="topic-tag">{{ topic }}</span>
                {% endfor %}
            </div>
            {% endif %}
        </div>
    </header>

    {% if post.summary %}
    <section class="post-summary">
        <h2>📋 Resumo</h2>
        <div class="summary-content">
            {{ post.summary | markdown }}
        </div>
    </section>
    {% endif %}

    <section class="post-content">
        <h2>💬 Conversas</h2>
        {% include 'components/message-timeline.html' %}
    </section>

    {% if post.enrichment %}
    <section class="post-enrichment">
        <h2>🔗 Conteúdo Compartilhado</h2>
        {% for item in post.enrichment %}
        {% include 'components/enriched-item.html' %}
        {% endfor %}
    </section>
    {% endif %}

    {% if post.media %}
    <section class="post-media">
        <h2>📸 Mídia</h2>
        {% include 'components/media-gallery.html' %}
    </section>
    {% endif %}
</article>

<nav class="post-navigation">
    {% if navigation.previous %}
    <a href="{{ navigation.previous.url }}" class="nav-previous">
        ← {{ navigation.previous.date | format_date('short') }}
    </a>
    {% endif %}
    
    {% if navigation.next %}
    <a href="{{ navigation.next.url }}" class="nav-next">
        {{ navigation.next.date | format_date('short') }} →
    </a>
    {% endif %}
</nav>
{% endblock %}
```

### 5. Theme Configuration

```toml
# egregora.toml
[site]
theme = "default"
title = "Rationality Club LatAm Reports"
description = "Daily conversations and insights"
language = "pt-BR"
base_url = "https://reports.rationality-club.org"

[site.themes.default]
primary_color = "#2563eb"
accent_color = "#7c3aed"
font_family = "Inter, sans-serif"
show_participants = true
show_media_gallery = true
enable_search = true

[site.themes.minimal]
primary_color = "#1f2937"
accent_color = "#059669" 
font_family = "system-ui, sans-serif"
show_participants = false
show_media_gallery = false
enable_search = false

[output.html]
theme = "default"
generate_feeds = true
generate_sitemap = true
minify_assets = true
```

### 6. Template Integration in Pipeline

```python
class EnhancedOutputManager:
    """Output manager with Jinja2 template support."""
    
    def __init__(self, config: SiteConfig):
        self.config = config
        self.template_engine = SiteTemplateEngine(
            template_dir=Path("templates"),
            theme=config.theme
        )
    
    def generate_daily_post(self, post_data: PostData) -> str:
        """Generate daily post using template."""
        
        context = {
            'post': post_data,
            'site': self.config,
            'navigation': self.build_navigation(post_data),
            'url_for': self.url_for,
        }
        
        return self.template_engine.render_template('daily.html', **context)
    
    def generate_site_index(self, groups: List[GroupData]) -> str:
        """Generate site homepage."""
        
        context = {
            'site': self.config,
            'groups': groups,
            'recent_posts': self.get_recent_posts(),
            'statistics': self.calculate_statistics(),
        }
        
        return self.template_engine.render_template('index.html', **context)
```

### 7. Separate Site vs Documentation

```
egregora/                      # System repository
├── src/egregora/             # System code
├── docs/                     # TECHNICAL documentation only
│   ├── developer-guide/
│   ├── user-guide/
│   └── api-reference/
├── templates/                # Site generation templates
│   ├── themes/
│   └── shared/
└── tests/

generated-sites/              # Generated site output (separate repo)
├── index.html               # Generated site homepage
├── daily/
│   ├── 2024-03-15.html
│   └── index.html
├── weekly/
├── assets/                  # Compiled CSS/JS from templates
└── feeds/
    ├── daily.xml
    └── weekly.xml
```

## Expected Benefits

1. **Clean Separation**: Site generation vs system documentation
2. **Customization**: Easy theming and layout changes
3. **Maintainability**: Templates easier to modify than Python code
4. **Multi-Site Support**: Different themes for different groups
5. **Designer Friendly**: HTML/CSS instead of Python for styling
6. **Professional Output**: Consistent, polished site generation

## Acceptance Criteria

- [ ] Jinja2 template engine integrated
- [ ] Default theme with responsive design
- [ ] Template inheritance system working
- [ ] Custom filters for Egregora-specific formatting
- [ ] Theme switching via configuration
- [ ] Separate template directory structure
- [ ] Asset compilation and optimization
- [ ] Documentation vs site content clearly separated

## Implementation Phases

### Phase 1: Template Engine
- Integrate Jinja2 with existing output system
- Create basic template structure
- Implement default theme

### Phase 2: Theme System
- Multiple theme support
- Asset compilation pipeline
- Theme configuration options

### Phase 3: Advanced Features
- Component library
- Email templates
- Theme marketplace/sharing

## Files to Create/Modify

### New Files
- `templates/themes/default/` - Default theme templates
- `src/egregora/templates/` - Template engine module
- `src/egregora/themes.py` - Theme management
- `docs/themes.md` - Theme development guide

### Modified Files
- `src/egregora/output/` - Integrate template engine
- `src/egregora/config.py` - Site and theme configuration
- `pyproject.toml` - Add Jinja2 dependency

## Related Issues

- #010: Architecture Separation (site vs documentation)
- #008: Output Formats (HTML generation enhancement)
- #007: Media Handling (media templates)

## Theme Ideas

### Default Theme
- Clean, modern design
- Responsive layout
- Full feature set
- Good for most use cases

### Minimal Theme  
- Lightweight, fast loading
- Basic styling only
- Focus on content
- Good for simple sites

### Corporate Theme
- Professional appearance
- Branded styling
- Advanced layouts
- Good for organizations

### Newsletter Theme
- Email-optimized layouts
- Print-friendly styles
- Simplified navigation
- Good for distribution