# Egregora Agent Configuration - {{ site_name }}

This directory contains file-based configuration for your site's AI agents. Power users can customize agent behavior by editing these files without touching Python code.

## Directory Structure

```
.egregora/
├── agents/          # Agent definitions (Jinja templates with YAML frontmatter)
│   ├── writer.jinja    # Writer agent configuration
│   ├── editor.jinja    # Editor agent configuration
│   ├── ranking.jinja   # Ranking agent configuration
│   └── ...
├── skills/          # Reusable prompt components
│   ├── summary.jinja
│   ├── diversity_first.jinja
│   └── redact.md
├── tools/           # Tool profiles and quotas
│   └── profiles.yaml
└── global/          # Global settings
    ├── seeds.yaml      # Default random seeds
    └── signing.yaml    # Trusted signing keys
```

## Agent Files

Agent files use Jinja2 templates with YAML frontmatter for configuration:

```jinja
{#---
agent_id: writer_v1
model: gemini-1.5-flash
seed: 42
ttl: 24h
variables:
  defaults: { max_tokens: 1000 }
  allowed: [max_tokens, site_name]
tools:
  use_profiles: [minimal]
  allow: [write_post, read_profile]
  deny: []
skills:
  enable: [summary]
env:
  timezone: UTC
#---#}

Your agent prompt goes here...
Use Jinja variables: {{ max_tokens }}
```

### Frontmatter Fields

- **agent_id**: Unique identifier with version (e.g., "writer_v1")
- **model**: Gemini model to use (e.g., "gemini-1.5-flash", "gemini-1.5-pro")
- **seed**: Random seed for reproducibility (null for random)
- **ttl**: Time-to-live for agent configuration cache
- **variables**:
  - `defaults`: Default values for template variables
  - `allowed`: List of variables that can be overridden at runtime
- **tools**:
  - `use_profiles`: Predefined tool profiles from `tools/profiles.yaml`
  - `allow`: Explicitly allowed tools
  - `deny`: Explicitly denied tools
- **skills**:
  - `enable`: List of skill templates to include from `skills/`
- **env**: Environment variables accessible in the template

## Customizing Agents

### 1. Change the Model

Edit the `model` field in the frontmatter:

```yaml
model: gemini-1.5-pro  # Use Pro for more complex tasks
```

### 2. Modify the Prompt

Edit the Jinja template below the frontmatter. You have full control over the system prompt.

### 3. Add/Remove Tools

Control which tools the agent can use:

```yaml
tools:
  allow: [write_post, read_profile]  # Only these tools
  deny: [generate_banner]            # Explicitly forbidden
```

### 4. Enable Skills

Skills are reusable prompt components from `.egregora/skills/`:

```yaml
skills:
  enable: [summary, diversity_first]
```

The skill content will be injected into your prompt template.

### 5. Set Variables

Define variables with defaults and runtime overrides:

```yaml
variables:
  defaults:
    max_posts: 3
    tone: "casual"
  allowed:
    - max_posts  # Can be overridden at runtime
    - tone
```

## How It Works

1. **Optional Layer**: The config system is **optional**. If no `.egregora/agents/*.jinja` file exists, Egregora uses the default Pydantic AI agents in `src/egregora/generation/*/pydantic_agent.py`.

2. **Runtime Loading**: When an agent runs, Egregora checks for a matching `.jinja` config file. If found, it loads the config and uses it to customize the agent.

3. **Configuration Hashing**: Agent configurations are hashed (SHA256) to track versions and ensure reproducibility.

4. **Backward Compatible**: Existing Egregora installations work without any `.egregora/` files.

## Example: Customizing the Writer

To customize the Writer agent, edit `.egregora/agents/writer.jinja`:

```jinja
{#---
agent_id: writer_v1
model: gemini-1.5-pro  # Use Pro for better writing
seed: 42               # Reproducible outputs
tools:
  allow: [write_post, read_profile, generate_banner]
#---#}

You are an expert technical writer for the Egregora blog.

Write in a clear, engaging style. Use concrete examples and metaphors.
Aim for {{ max_posts | default(2) }} posts per period.

{{ markdown_table }}
```

## Available Tools by Agent

### Writer Agent
- `write_post`: Create a blog post with frontmatter
- `read_profile`: Read author profile
- `write_profile`: Update author profile
- `search_media`: Search for relevant media
- `annotate_conversation`: Add metadata to conversations
- `generate_banner`: Create meme images

### Editor Agent
- `edit_line`: Replace a single line
- `full_rewrite`: Replace entire document
- `query_rag`: Search previous posts
- `ask_llm`: Consult another LLM
- `finish`: Mark editing complete

### Ranking Agent
- `choose_winner`: Select better post
- `comment_on_post`: Provide editorial commentary

## Tool Profiles

Tool profiles in `.egregora/tools/profiles.yaml` define preset tool configurations:

```yaml
minimal:
  allow: [write_post, read_profile]
  deny: [generate_banner]
  quotas:
    write_post: 5
    read_profile: 10
```

Use in agent config:

```yaml
tools:
  use_profiles: [minimal]
```

## Skills

Skills in `.egregora/skills/` are reusable prompt components:

**summary.jinja**:
```jinja
## Summarization Guidelines
- Extract key points
- Use bullet format
- Max 3 sentences
```

Enable in agent:

```yaml
skills:
  enable: [summary]
```

The skill content is injected into your prompt template automatically.

## Security Considerations

⚠️ **Template Injection Warning**: Agent templates use Jinja2 and have access to all template variables. The templates are executed with full Jinja2 capabilities, which means they can access Python objects and call methods.

**Important security guidelines:**
- Only use agent configurations from trusted sources
- Do not run `egregora` commands on `.egregora` directories from untrusted repositories without reviewing the template files first
- Be cautious when cloning repositories that include `.egregora/` configurations
- Review all Jinja2 templates (`.jinja` files) before using them, especially if shared by others

If you're sharing your Egregora site configuration publicly, ensure your `.egregora/` templates don't contain sensitive information or dangerous code.

## Best Practices

1. **Version Your Agents**: Use version suffixes in `agent_id` (e.g., "writer_v2")
2. **Test Changes**: Run `egregora edit` or `egregora process` to test your configs
3. **Track Configs**: Commit `.egregora/` to version control
4. **Start Simple**: Begin with small prompt tweaks before major changes
5. **Use Skills**: Extract reusable prompt components into skills
6. **Profile Tools**: Use tool profiles for consistent tool configurations
7. **Review Shared Configs**: Always review `.egregora/` files from other sources before using them

## Troubleshooting

**Config not loading?**
- Check file name matches agent name (e.g., `writer.jinja` for writer agent)
- Verify YAML frontmatter is valid (use `---` delimiters)
- Check for Jinja syntax errors

**Agent behaving unexpectedly?**
- Review which tools are enabled/disabled
- Check variable defaults and overrides
- Verify model selection (Pro vs Flash)

**Want default behavior?**
- Delete or rename the `.jinja` file
- Egregora will use built-in Pydantic AI agents

## Future Enhancements

- Web UI for editing agent configs
- Agent config validation tool
- Prompt library and templates
- A/B testing framework for prompts
- Agent performance analytics

---

For more information, see:
- [Pydantic AI Migration Documentation](../docs/development/pydantic-ai-migration-complete.md)
- [Egregora Architecture Guide](../docs/guides/architecture.md)
