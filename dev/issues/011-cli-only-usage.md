# Issue #011: Enhanced CLI-Only Usage (No TOML Required)

## Priority: Medium
## Effort: Low
## Type: Enhancement

## Problem Description

While Egregora already supports pip installation and has environment variable configuration, the CLI-only usage experience could be significantly improved:

1. **Documentation Gap**: Limited documentation on TOML-free usage
2. **Setup Complexity**: Users still think TOML is required
3. **Missing CLI Flags**: Some config options only available via TOML
4. **Poor Discovery**: Environment variable names not well documented
5. **No Setup Wizard**: No guided setup for CLI-only users

**Current state:**
- ✅ `pip install egregora` works
- ✅ Environment variables supported via pydantic-settings
- ✅ CLI entry point configured
- ❌ Poor documentation for TOML-free usage
- ❌ Some advanced options only in TOML
- ❌ No setup assistance for new users

## Current Behavior

### What Works Today
```bash
# Already functional
pip install egregora
export EGREGORA_ZIPS_DIR="/path/to/zips"
export EGREGORA_POSTS_DIR="/path/to/output"
export GEMINI_API_KEY="your-key"
egregora --days 7
```

### What's Missing
- CLI flags for common configuration options
- Environment variable documentation
- Setup wizard for first-time users
- Validation of CLI-only setup

## Proposed Solution

### 1. Expanded CLI Flags

```python
# Enhanced CLI with more configuration options
@app.command()
def main(
    config: Annotated[Path | None, typer.Option(
        "--config", "-c",
        help="Configuration file path (optional)",
        callback=_validate_config_file
    )] = None,
    
    # Directory options
    zips_dir: Annotated[Path | None, typer.Option(
        "--zips-dir",
        help="Directory containing WhatsApp ZIP exports"
    )] = None,
    
    posts_dir: Annotated[Path | None, typer.Option(
        "--posts-dir", 
        help="Directory to save generated posts"
    )] = None,
    
    # Processing options
    days: Annotated[int | None, typer.Option(
        "--days",
        help="Number of days to process (default: all available)"
    )] = None,
    
    group_name: Annotated[str | None, typer.Option(
        "--group",
        help="Specific group to process"
    )] = None,
    
    # AI options
    model: Annotated[str | None, typer.Option(
        "--model",
        help="AI model to use (default: gemini-flash-lite-latest)"
    )] = None,
    
    language: Annotated[str | None, typer.Option(
        "--language",
        help="Post language (pt-BR, en-US, etc.)"
    )] = None,
    
    # Feature flags
    disable_enrichment: Annotated[bool, typer.Option(
        "--disable-enrichment",
        help="Disable content enrichment (faster, no API calls for links)"
    )] = False,
    
    demo_mode: Annotated[bool, typer.Option(
        "--demo-mode",
        help="Run in demo mode (no API key required, uses templates)"
    )] = False,
    
    # Output options
    output_format: Annotated[list[str] | None, typer.Option(
        "--format",
        help="Output formats: markdown, html, json (can specify multiple)"
    )] = None,
    
    # Privacy options
    privacy_level: Annotated[str | None, typer.Option(
        "--privacy",
        help="Privacy level: minimal, standard, high, maximum"
    )] = None,
    
    # Utility flags
    dry_run: Annotated[bool, typer.Option(
        "--dry-run",
        help="Show what would be processed without executing"
    )] = False,
    
    verbose: Annotated[bool, typer.Option(
        "--verbose", "-v",
        help="Verbose output for debugging"
    )] = False,
):
    """🗣️ Generate daily posts from WhatsApp exports."""
```

### 2. Setup Wizard Command

```python
@app.command()
def init(
    interactive: Annotated[bool, typer.Option(
        "--interactive", "-i",
        help="Interactive setup wizard"
    )] = True,
):
    """🚀 Initialize Egregora configuration."""
    
    console.print("🗣️ Egregora Setup Wizard")
    
    config_method = typer.prompt(
        "Configuration method",
        type=click.Choice(['env', 'toml', 'cli-only']),
        default='env'
    )
    
    if config_method == 'env':
        setup_environment_variables()
    elif config_method == 'toml':
        setup_toml_configuration()
    else:
        setup_cli_only_usage()

def setup_environment_variables():
    """Guide user through environment variable setup."""
    
    zips_dir = typer.prompt("WhatsApp exports directory", default="./whatsapp_zips")
    posts_dir = typer.prompt("Output directory", default="./posts")
    
    api_key_setup = typer.confirm("Do you have a Gemini API key?")
    
    env_content = f"""# Egregora Configuration
EGREGORA_ZIPS_DIR="{zips_dir}"
EGREGORA_POSTS_DIR="{posts_dir}"
{"GEMINI_API_KEY=your-key-here" if not api_key_setup else ""}
"""
    
    Path(".env").write_text(env_content)
    console.print("✅ Configuration saved to .env")
```

### 3. Environment Variable Documentation

```python
@app.command()
def env_help():
    """📋 Show all supported environment variables."""
    
    env_table = Table(title="Egregora Environment Variables")
    env_table.add_column("Variable", style="cyan")
    env_table.add_column("Description", style="white")
    env_table.add_column("Default", style="dim")
    
    env_vars = [
        ("GEMINI_API_KEY", "Gemini API key (required)", "None"),
        ("EGREGORA_ZIPS_DIR", "WhatsApp exports directory", "data/whatsapp_zips"),
        ("EGREGORA_POSTS_DIR", "Output directory", "data"),
        ("EGREGORA_MODEL", "AI model name", "gemini-flash-lite-latest"),
        ("EGREGORA_POST_LANGUAGE", "Output language", "pt-BR"),
        ("EGREGORA_DEMO_MODE", "Enable demo mode", "false"),
    ]
    
    for var, desc, default in env_vars:
        env_table.add_row(var, desc, default)
    
    console.print(env_table)
```

### 4. Configuration Check Command

```python
@app.command()  
def check():
    """🔍 Validate current configuration and environment."""
    
    console.print("🔍 Configuration Check")
    
    # Check API key
    api_key = os.getenv('GEMINI_API_KEY')
    if api_key:
        console.print("✅ GEMINI_API_KEY: Set")
    else:
        console.print("⚠️  GEMINI_API_KEY: Not set (demo mode required)")
    
    # Check directories
    zips_dir = os.getenv('EGREGORA_ZIPS_DIR', 'data/whatsapp_zips')
    posts_dir = os.getenv('EGREGORA_POSTS_DIR', 'data')
    
    console.print(f"📋 EGREGORA_ZIPS_DIR: {zips_dir}")
    console.print(f"📋 EGREGORA_POSTS_DIR: {posts_dir}")
    
    if Path(zips_dir).exists():
        console.print("✅ Zips directory exists")
    else:
        console.print("❌ Zips directory not found")
```

## Expected Benefits

1. **Lower Barrier to Entry**: Users can try immediately after pip install
2. **Better Discovery**: Clear documentation of CLI options
3. **Flexible Configuration**: Multiple configuration methods
4. **Setup Assistance**: Guided setup for new users
5. **Self-Documenting**: Built-in help commands

## Acceptance Criteria

- [ ] All major configuration options available as CLI flags
- [ ] Interactive setup wizard (`egregora init`)
- [ ] Environment variable documentation (`egregora env-help`)
- [ ] Configuration validation (`egregora check`)
- [ ] Updated documentation with CLI-only examples
- [ ] Backward compatibility with existing TOML configurations

## Files to Modify

- `src/egregora/__main__.py` - Enhanced CLI with more flags
- `docs/cli-usage.md` - New CLI-only documentation
- `README.md` - Add quick start without TOML

## Related Issues

- #001: Offline/Demo Mode (demo mode via CLI flag)
- #002: Configuration UX (setup wizard integration)
- #010: Architecture Separation (external data directory)