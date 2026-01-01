# CLI Reference

The Egregora command-line interface provides commands for running the content generation pipeline, managing the site, and evaluating posts.

## Overview

Egregora uses [Typer](https://typer.tiangolo.com/) for its CLI. The main entrypoint is `egregora`, with subcommands for different operations:

- **Main commands**: `write`, `init`, `diagnostics`, `show`
- **Read commands**: `read` - Evaluate and rank blog posts using the reader agent

All commands support `--help` for detailed usage information.

## Main CLI Application

::: egregora.cli.main
    options:
      show_source: false
      show_root_heading: true
      heading_level: 2
      members_order: source
      show_if_no_docstring: false

## Read Command

The `read` subcommand provides post evaluation and ranking functionality.

::: egregora.cli.read
    options:
      show_source: false
      show_root_heading: true
      heading_level: 2
      members_order: source
      show_if_no_docstring: false

## Usage Examples

### Initialize a New Site

```bash
# Create a new Egregora site
egregora init ./my-blog

# Initialize with a specific site identifier
egregora init ./my-blog --site my-site
```

### Run the Pipeline

```bash
# Process WhatsApp export and generate content
egregora write ./my-blog \
  --source whatsapp \
  --source-path ./whatsapp-export \
  --window-size 7 \
  --window-unit days

# Use a specific model
egregora write ./my-blog \
  --source whatsapp \
  --source-path ./whatsapp-export \
  --model gemini-2.0-flash-exp
```

### Evaluate Posts

```bash
# Run reader agent to evaluate and rank posts
egregora read ./my-blog

# Use a specific model for evaluation
egregora read ./my-blog --model gemini-2.0-flash-exp

# Evaluate a specific site in multi-site config
egregora read ./my-blog --site my-site
```

### Run Diagnostics

```bash
# Check system health and dependencies
egregora diagnostics

# Diagnose a specific site
egregora diagnostics ./my-blog
```

### Show Information

```bash
# Show available sources
egregora show sources

# Show available models
egregora show models

# Show Elo rankings
egregora show elo ./my-blog
```

## Common Options

Most commands support these common options:

- `--site`: Site identifier for multi-site configurations
- `--model`: Override the AI model (e.g., `gemini-2.0-flash-exp`)
- `--verbose` / `-v`: Enable verbose logging
- `--help`: Show detailed help for the command
