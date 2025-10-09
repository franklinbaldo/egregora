# Issue #010: Architectural Separation - Generator vs Generated Site

## Priority: High
## Effort: High
## Type: Architecture Refactoring

## Problem Description

Currently, the Egregora system suffers from poor separation of concerns, mixing the generator system, generated content, documentation, and data storage in a single repository structure. This creates several issues:

1. **Conflated Purposes**: Documentation system serves both technical docs and public website
2. **Mixed Content**: Generated posts mixed with source code in version control
3. **Security Risk**: Sensitive data (cache, profiles) stored within code repository
4. **Deployment Confusion**: No clear separation between system deployment and content publishing
5. **Scaling Issues**: Single repository becomes unwieldy as content grows

**Current problematic structure:**
```
egregora/
├── docs/index.md              # Public website content, not technical docs
├── data/rationality-club/     # Generated content mixed with source
├── src/egregora/              # Generator system code
└── cache/                     # Sensitive data in code repo
```

## Current Behavior

### Mixed Repository Structure
- Technical documentation mixed with public website content
- Generated posts stored in same repo as source code
- MkDocs serves both developer docs and public site
- Data files versioned alongside code

### Deployment Issues
- No clear separation between system updates and content updates
- Difficult to deploy generated site independently
- Cache and sensitive data exposed in repository
- Single CI/CD pipeline for different concerns

### Scaling Problems
- Repository size grows with every generated post
- Git history polluted with content changes
- Difficult to manage access permissions (code vs content)
- No clear data retention policies

## Proposed Solution

### 1. Three-Repository Architecture

#### A. Generator System Repository (`egregora`)
```
egregora/
├── src/egregora/              # Core system code
├── docs/                      # TECHNICAL documentation only
│   ├── developer-guide/
│   ├── user-guide/
│   ├── installation.md
│   └── api-reference.md
├── tests/
├── templates/                 # Output templates
├── pyproject.toml
└── README.md                  # System documentation
```

#### B. Generated Site Repository (`egregora-sites/{group-name}`)
```
rationality-club-reports/      # Separate repository
├── index.html                 # Public website entry point
├── daily/
│   ├── 2024-03-15.html
│   ├── 2024-03-16.html
│   └── index.html             # Daily reports index
├── weekly/
│   └── index.html
├── monthly/
│   └── index.html
├── assets/
│   ├── css/
│   ├── js/
│   └── media/                 # Optimized media files
├── feed.xml                   # RSS feed
├── sitemap.xml
└── .gitignore                 # Exclude sensitive generated files
```

#### C. Data Storage (External)
```
/var/egregora-data/           # Outside version control
├── groups/
│   └── rationality-club/
│       ├── zips/             # WhatsApp exports
│       ├── cache/            # Enrichment cache
│       ├── profiles/         # Participant profiles
│       └── raw-posts/        # Pre-processed content
├── config/
│   ├── egregora.toml
│   └── secrets.env
└── logs/
    ├── processing.log
    └── privacy_audit.log
```

### 2. Deployment Pipeline Separation

#### System Deployment
```yaml
# egregora/.github/workflows/deploy-system.yml
name: Deploy Egregora System
on:
  push:
    branches: [main]
    paths: ['src/**', 'pyproject.toml']

jobs:
  deploy-system:
    - name: Build and test system
    - name: Deploy to processing environment
    - name: Update system documentation
```

#### Content Generation & Publication
```yaml
# egregora/.github/workflows/generate-content.yml
name: Generate and Publish Content
on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM
  workflow_dispatch:

jobs:
  generate-content:
    - name: Checkout generator system
    - name: Run content generation
    - name: Checkout site repository
    - name: Update generated content
    - name: Deploy to GitHub Pages/Netlify
```

### 3. Configuration Changes

#### System Configuration (`egregora.toml`)
```toml
[deployment]
# Separate data and output locations
data_dir = "/var/egregora-data"
output_repository = "git@github.com:org/rationality-club-reports.git"
site_base_url = "https://reports.rationality-club.org"

[publishing]
auto_commit = true
auto_deploy = true
deploy_target = "github-pages"  # or "netlify", "s3", etc.

[directories]
# All paths now relative to data_dir
zips_dir = "groups/{group}/zips"
cache_dir = "cache"
posts_dir = "groups/{group}/raw-posts"
profiles_dir = "groups/{group}/profiles"

[output]
# Output goes to separate repository
site_repo_dir = "/tmp/egregora-sites/{group}"
formats = ["html", "json", "rss"]
```

### 4. Enhanced CLI for Multi-Repository Management

```python
class RepositoryManager:
    """Manage multiple repositories for Egregora deployment."""
    
    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.site_repo = None
    
    def setup_site_repository(self, group_name: str) -> Path:
        """Clone or initialize site repository."""
        repo_url = self.config.output_repository.format(group=group_name)
        local_path = Path(f"/tmp/egregora-sites/{group_name}")
        
        if local_path.exists():
            # Pull latest changes
            repo = git.Repo(local_path)
            repo.remotes.origin.pull()
        else:
            # Clone repository
            git.Repo.clone_from(repo_url, local_path)
        
        return local_path
    
    def publish_content(self, generated_content: Dict[str, Path], group_name: str):
        """Publish generated content to site repository."""
        site_path = self.setup_site_repository(group_name)
        
        # Copy generated files
        for content_type, source_path in generated_content.items():
            dest_path = site_path / content_type
            shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
        
        # Commit and push changes
        repo = git.Repo(site_path)
        repo.git.add(all=True)
        repo.index.commit(f"Update {group_name} content - {datetime.now().isoformat()}")
        repo.remotes.origin.push()

# CLI integration
@click.command()
@click.option('--group', required=True, help='Group to generate content for')
@click.option('--publish', is_flag=True, help='Automatically publish to site repository')
def generate(group: str, publish: bool):
    """Generate content with optional publishing."""
    
    # Generate content
    processor = UnifiedProcessor(config)
    generated_content = processor.process_group(group)
    
    if publish:
        repo_manager = RepositoryManager(config.deployment)
        repo_manager.publish_content(generated_content, group)
        console.print(f"✅ Content published to {config.deployment.site_base_url}")
    else:
        console.print(f"✅ Content generated locally. Use --publish to deploy.")
```

### 5. Site Template System

#### Base Site Template
```html
<!-- templates/site/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ site.title }} - {{ page.title }}</title>
    <link rel="stylesheet" href="{{ url_for('assets', filename='css/main.css') }}">
    <link rel="alternate" type="application/rss+xml" href="{{ url_for('feed.xml') }}">
</head>
<body>
    <header class="site-header">
        <nav class="site-nav">
            <a href="{{ url_for('index.html') }}">{{ site.title }}</a>
            <a href="{{ url_for('daily/index.html') }}">Daily Reports</a>
            <a href="{{ url_for('weekly/index.html') }}">Weekly Summaries</a>
            <a href="{{ url_for('monthly/index.html') }}">Monthly Archives</a>
        </nav>
    </header>
    
    <main class="site-content">
        {% block content %}{% endblock %}
    </main>
    
    <footer class="site-footer">
        <p>Generated by <a href="https://github.com/org/egregora">Egregora</a></p>
        <p>Last updated: {{ site.last_updated.strftime('%Y-%m-%d %H:%M UTC') }}</p>
    </footer>
</body>
</html>
```

### 6. Security and Access Control

#### Data Directory Permissions
```bash
# Setup secure data directory
sudo mkdir -p /var/egregora-data
sudo chown egregora:egregora /var/egregora-data
sudo chmod 750 /var/egregora-data

# Separate sensitive from public data
/var/egregora-data/
├── sensitive/          # 700 permissions
│   ├── zips/
│   ├── cache/
│   └── profiles/
└── public/            # 755 permissions
    └── generated/
```

#### Repository Access Control
```yaml
# Site repository settings
egregora-sites/rationality-club-reports:
  private: false          # Public site repository
  pages: enabled         # GitHub Pages deployment
  
# Generator repository settings  
egregora:
  private: true          # Private system repository
  teams:
    - developers: admin
    - content-managers: read
```

## Expected Benefits

1. **Clear Separation**: Distinct repositories for code, content, and data
2. **Better Security**: Sensitive data outside version control
3. **Independent Deployment**: System updates don't affect content publishing
4. **Scalability**: Content repositories can grow without affecting system repo
5. **Access Control**: Different permissions for system vs content management
6. **Professional Structure**: Industry-standard separation of concerns

## Implementation Phases

### Phase 1: Repository Separation
- Create separate site repository template
- Move generated content out of main repo
- Update configuration for external data directory

### Phase 2: Deployment Pipeline
- Implement RepositoryManager class
- Create GitHub Actions for content generation
- Setup automated publishing workflow

### Phase 3: Enhanced Features
- Multi-site management
- Advanced deployment targets
- Content management dashboard

## Migration Plan

### Step 1: Backup Current State
```bash
# Backup existing generated content
cp -r egregora/data/ /backup/egregora-content/
cp -r egregora/docs/ /backup/egregora-docs/
```

### Step 2: Create New Repositories
```bash
# Create site repository
gh repo create org/rationality-club-reports --public
git clone git@github.com:org/rationality-club-reports.git

# Initialize with generated content
egregora migrate-to-site-repo rationality-club-reports
```

### Step 3: Update System Configuration
```bash
# Move data to external location
sudo mkdir -p /var/egregora-data
sudo mv egregora/data/* /var/egregora-data/groups/rationality-club/

# Update configuration
egregora config migrate-paths
```

### Step 4: Test New Architecture
```bash
# Test content generation with new structure
egregora generate --group rationality-club --publish --dry-run
```

## Acceptance Criteria

- [ ] Separate repositories for generator system and generated sites
- [ ] External data directory outside version control
- [ ] Automated content generation and publishing pipeline
- [ ] Technical documentation separated from public website
- [ ] Migration script for existing installations
- [ ] Secure file permissions for sensitive data
- [ ] Multi-site support for different groups
- [ ] Independent deployment of system vs content updates

## Files to Create/Modify

### New Files
- `src/egregora/deployment/repository_manager.py`
- `src/egregora/cli/migrate.py`
- `templates/site/` directory structure
- `.github/workflows/generate-content.yml`
- `docs/deployment-architecture.md`

### Modified Files
- `src/egregora/config.py` - Add deployment configuration
- `src/egregora/__main__.py` - Add migration and publishing commands
- `src/egregora/processor.py` - Update output paths
- `docs/` - Remove non-technical content

### Removed/Moved Content
- Move `docs/index.md` public content to site template
- Remove `data/` from repository
- Move generated content to separate repositories

## Related Issues

- #002: Configuration UX (simplified config for new architecture)
- #008: Output Formats (enhanced for multi-repository deployment)
- #009: Privacy & Security (secure data directory structure)
- #011: Multi-User Support (per-group site repositories)

## Breaking Changes

⚠️ **This is a major architectural change that will require:**
- Data migration for existing installations
- Updated deployment procedures
- New configuration format
- Separate repository management

Existing users will need to follow the migration guide to update their installations.