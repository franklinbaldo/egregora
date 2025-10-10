# Output Formats

## Priority: Low
## Effort: Medium
## Type: Enhancement

## Problem Description

Currently, Egregora only outputs Markdown posts, limiting its utility for different use cases and integrations:

1. **Single Format**: Only Markdown output available
2. **Limited Integration**: Hard to integrate with other systems
3. **No Web View**: No HTML output for direct web consumption
4. **Missing Export Options**: No structured data formats (JSON, CSV)
5. **Static Output**: No interactive features or dynamic content

**Current output:**
- Markdown files in `data/<group>/posts/daily/YYYY-MM-DD.md`
- Basic structure with anonymized content
- No alternative formats or views

## Current Behavior

### Single Output Format
```
data/rationality-club-latam/posts/daily/
├── 2024-03-15.md
├── 2024-03-16.md
└── 2024-03-17.md
```

### Limited Consumption Options
- Must process Markdown for web display
- No API-friendly formats
- No print-optimized layouts
- No interactive features

## Proposed Solution

### 1. Multi-Format Output System

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class OutputFormatter(ABC):
    """Abstract base for output formatters."""
    
    @abstractmethod
    def format_post(self, post_data: PostData) -> str:
        """Format post data into specific output format."""
        pass
    
    @abstractmethod
    def get_file_extension(self) -> str:
        """Get file extension for this format."""
        pass

class MarkdownFormatter(OutputFormatter):
    """Current Markdown formatter."""
    
    def format_post(self, post_data: PostData) -> str:
        return self.render_markdown_template(post_data)
    
    def get_file_extension(self) -> str:
        return ".md"

class HTMLFormatter(OutputFormatter):
    """HTML formatter for web consumption."""
    
    def __init__(self, theme: str = "default"):
        self.theme = theme
        self.template_env = self.setup_jinja_env()
    
    def format_post(self, post_data: PostData) -> str:
        template = self.template_env.get_template(f"post_{self.theme}.html")
        return template.render(
            post=post_data,
            media_files=self.get_media_files(post_data),
            navigation=self.build_navigation(post_data)
        )
    
    def get_file_extension(self) -> str:
        return ".html"

class JSONFormatter(OutputFormatter):
    """JSON formatter for API consumption."""
    
    def format_post(self, post_data: PostData) -> str:
        return json.dumps({
            'group': post_data.group_name,
            'date': post_data.date.isoformat(),
            'summary': post_data.summary,
            'participants': post_data.participants,
            'messages': [
                {
                    'timestamp': msg.timestamp.isoformat(),
                    'sender': msg.sender,
                    'content': msg.content,
                    'type': msg.type
                }
                for msg in post_data.messages
            ],
            'enrichment': post_data.enrichment_data,
            'metadata': post_data.metadata
        }, indent=2, ensure_ascii=False)
    
    def get_file_extension(self) -> str:
        return ".json"
```

### 2. HTML Templates with Themes

```html
<!-- templates/html/post_default.html -->
<!DOCTYPE html>
<html lang="{{ post.language }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ post.group_name }} - {{ post.date.strftime('%Y-%m-%d') }}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/post.css') }}">
</head>
<body>
    <header class="post-header">
        <h1>{{ post.group_name }}</h1>
        <time datetime="{{ post.date.isoformat() }}">
            {{ post.date.strftime('%B %d, %Y') }}
        </time>
        <div class="stats">
            <span>{{ post.message_count }} messages</span>
            <span>{{ post.participants|length }} participants</span>
        </div>
    </header>

    <main class="post-content">
        <!-- Executive Summary -->
        <section class="summary">
            <h2>📋 Summary</h2>
            <div class="summary-content">
                {{ post.summary | markdown }}
            </div>
        </section>

        <!-- Key Topics -->
        {% if post.key_topics %}
        <section class="topics">
            <h2>🏷️ Key Topics</h2>
            <div class="topic-tags">
                {% for topic in post.key_topics %}
                <span class="topic-tag">{{ topic }}</span>
                {% endfor %}
            </div>
        </section>
        {% endif %}

        <!-- Messages Timeline -->
        <section class="timeline">
            <h2>💬 Conversation</h2>
            <div class="messages">
                {% for message in post.messages %}
                <div class="message" data-sender="{{ message.sender }}">
                    <div class="message-header">
                        <span class="sender">{{ message.sender }}</span>
                        <time>{{ message.timestamp.strftime('%H:%M') }}</time>
                    </div>
                    <div class="message-content">
                        {% if message.type == 'media' %}
                            {{ render_media(message) }}
                        {% else %}
                            {{ message.content | markdown }}
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>

        <!-- Enriched Content -->
        {% if post.enrichment_data %}
        <section class="enrichment">
            <h2>🔗 Shared Content</h2>
            {% for item in post.enrichment_data %}
            <div class="enriched-item">
                <h3><a href="{{ item.url }}" target="_blank">{{ item.title }}</a></h3>
                <p>{{ item.summary }}</p>
                <div class="tags">
                    {% for tag in item.tags %}
                    <span class="tag">{{ tag }}</span>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </section>
        {% endif %}
    </main>

    <footer class="post-footer">
        <div class="navigation">
            {% if navigation.previous %}
            <a href="{{ navigation.previous.url }}" class="nav-link">
                ← {{ navigation.previous.date.strftime('%m/%d') }}
            </a>
            {% endif %}
            {% if navigation.next %}
            <a href="{{ navigation.next.url }}" class="nav-link">
                {{ navigation.next.date.strftime('%m/%d') }} →
            </a>
            {% endif %}
        </div>
        <div class="metadata">
            Generated by <a href="https://github.com/your-org/egregora">Egregora</a>
        </div>
    </footer>
</body>
</html>
```

### 3. PDF Generation

```python
from weasyprint import HTML, CSS
from pathlib import Path

class PDFFormatter(OutputFormatter):
    """PDF formatter for print-friendly output."""
    
    def __init__(self, style: str = "print"):
        self.style = style
        self.html_formatter = HTMLFormatter(theme="print")
    
    def format_post(self, post_data: PostData) -> bytes:
        """Generate PDF from HTML."""
        # First generate HTML
        html_content = self.html_formatter.format_post(post_data)
        
        # Apply print-specific CSS
        css_path = Path(__file__).parent / "templates" / "css" / f"{self.style}.css"
        css = CSS(filename=str(css_path))
        
        # Generate PDF
        html_doc = HTML(string=html_content)
        pdf_bytes = html_doc.write_pdf(stylesheets=[css])
        
        return pdf_bytes
    
    def get_file_extension(self) -> str:
        return ".pdf"

# Usage
pdf_formatter = PDFFormatter()
pdf_content = pdf_formatter.format_post(post_data)

# Save PDF
pdf_path = output_dir / f"{post_data.date.strftime('%Y-%m-%d')}.pdf"
pdf_path.write_bytes(pdf_content)
```

### 4. RSS Feed Generation

```python
from feedgen.feed import FeedGenerator

class RSSFormatter:
    """Generate RSS feeds for group updates."""
    
    def __init__(self, group_name: str, base_url: str):
        self.group_name = group_name
        self.base_url = base_url
        self.fg = self.setup_feed()
    
    def setup_feed(self) -> FeedGenerator:
        fg = FeedGenerator()
        fg.title(f"{self.group_name} - Daily Updates")
        fg.description(f"Daily conversation summaries from {self.group_name}")
        fg.link(href=self.base_url, rel='alternate')
        fg.link(href=f"{self.base_url}/feed.xml", rel='self')
        fg.language('en')
        return fg
    
    def add_post(self, post_data: PostData):
        """Add post to RSS feed."""
        fe = self.fg.add_entry()
        fe.id(f"{self.base_url}/posts/{post_data.date.strftime('%Y-%m-%d')}")
        fe.title(f"{self.group_name} - {post_data.date.strftime('%Y-%m-%d')}")
        fe.description(post_data.summary)
        fe.link(href=f"{self.base_url}/posts/{post_data.date.strftime('%Y-%m-%d')}.html")
        fe.pubDate(post_data.date)
    
    def generate_feed(self) -> str:
        """Generate RSS XML."""
        return self.fg.rss_str(pretty=True).decode('utf-8')

# Usage
rss_formatter = RSSFormatter("Tech Group", "https://example.com")
for post in recent_posts:
    rss_formatter.add_post(post)

rss_xml = rss_formatter.generate_feed()
```

### 5. Multi-Format Configuration

```toml
[output]
# Enable multiple output formats
formats = ["markdown", "html", "json"]
# Optional formats that require additional dependencies
# formats = ["markdown", "html", "json", "pdf", "rss"]

[output.html]
theme = "default"  # default, minimal, dark
include_media = true
generate_index = true
base_url = "https://your-site.com"

[output.pdf] 
style = "print"    # print, compact, detailed
page_size = "A4"
include_images = false

[output.json]
include_raw_messages = false
include_metadata = true
pretty_print = true

[output.rss]
enabled = true
max_entries = 30
include_full_content = false
```

### 6. Output Manager

```python
class OutputManager:
    """Manage multiple output formats for posts."""
    
    def __init__(self, config: OutputConfig):
        self.config = config
        self.formatters = self.setup_formatters()
    
    def setup_formatters(self) -> Dict[str, OutputFormatter]:
        formatters = {}
        
        if "markdown" in self.config.formats:
            formatters["markdown"] = MarkdownFormatter()
        
        if "html" in self.config.formats:
            formatters["html"] = HTMLFormatter(self.config.html.theme)
        
        if "json" in self.config.formats:
            formatters["json"] = JSONFormatter()
        
        if "pdf" in self.config.formats:
            formatters["pdf"] = PDFFormatter(self.config.pdf.style)
        
        return formatters
    
    def generate_outputs(self, post_data: PostData, output_dir: Path):
        """Generate all configured output formats."""
        outputs_generated = []
        
        for format_name, formatter in self.formatters.items():
            try:
                content = formatter.format_post(post_data)
                filename = f"{post_data.date.strftime('%Y-%m-%d')}{formatter.get_file_extension()}"
                
                # Create format-specific directory
                format_dir = output_dir / format_name
                format_dir.mkdir(exist_ok=True)
                
                # Write output
                output_path = format_dir / filename
                if isinstance(content, bytes):
                    output_path.write_bytes(content)
                else:
                    output_path.write_text(content, encoding='utf-8')
                
                outputs_generated.append(output_path)
                logger.info(f"Generated {format_name}: {output_path}")
                
            except Exception as e:
                logger.error(f"Failed to generate {format_name} output: {e}")
        
        return outputs_generated
```

## Expected Benefits

1. **Flexibility**: Multiple output formats for different use cases
2. **Integration**: JSON/RSS for API and feed consumption
3. **User Experience**: HTML for direct web viewing
4. **Distribution**: PDF for sharing and printing
5. **Automation**: RSS for automated consumption

## Acceptance Criteria

- [ ] HTML output with responsive design and media support
- [ ] JSON export with complete structured data
- [ ] PDF generation with print-optimized layout
- [ ] RSS feed support for automated updates
- [ ] Configurable output formats per group
- [ ] Theme system for HTML output
- [ ] Navigation between posts in HTML format
- [ ] Media embedding in HTML and PDF outputs

## Implementation Phases

### Phase 1: Core Infrastructure
- Output formatter interface
- HTML formatter with basic theme
- JSON formatter

### Phase 2: Enhanced Formats
- PDF generation
- RSS feed support
- Advanced HTML themes

### Phase 3: Features & Polish
- Navigation systems
- Search functionality
- Export tools

## Files to Modify

- `src/egregora/output/` - New output system
- `src/egregora/config.py` - Output configuration
- `templates/` - HTML templates and themes
- `static/` - CSS and JavaScript assets
- `src/egregora/processor.py` - Integration with output manager
- `docs/output-formats.md` - Output documentation

## Related Issues

- #007: Media Handling (media in HTML/PDF outputs)
- #011: Multi-User Support (user-specific output preferences)
- #012: Monitoring & Analytics (output generation metrics)