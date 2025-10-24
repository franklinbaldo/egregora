# Installation

Get Egregora up and running in 5 minutes.

## Prerequisites

- **Python 3.11+** (required)
- **Google Gemini API key** ([Get one here](https://ai.google.dev/))
- **WhatsApp chat export** (see [How to Export](#how-to-export-whatsapp-chats))

## Install Egregora

### Option 1: Install from PyPI (Recommended)

```bash
pip install egregora
```

### Option 2: Install from Source

```bash
# Clone the repository
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# Install in development mode
pip install -e .
```

### Optional Dependencies

For documentation site generation and linting:

```bash
pip install 'egregora[docs,lint]'
```

## Verify Installation

```bash
egregora --help
```

You should see the CLI help message with available commands.

## Set Up API Key

Export your Gemini API key as an environment variable:

```bash
export GOOGLE_API_KEY="your-api-key-here"
```

Or pass it directly to commands:

```bash
egregora process --gemini_key="your-api-key-here" ...
```

## How to Export WhatsApp Chats

### On Android

1. Open the WhatsApp chat/group
2. Tap the three dots (⋮) → More → Export chat
3. Choose "Without Media" (faster) or "Include Media"
4. Save the ZIP file

### On iOS

1. Open the WhatsApp chat/group
2. Tap the contact/group name → Export Chat
3. Choose "Without Media" or "Attach Media"
4. Save the ZIP file via Files app or email

The export will be a `.zip` file containing:
- `_chat.txt` - Message history
- Media files (if included)

## Next Steps

- [Quickstart Tutorial](quickstart.md) - Create your first blog post
- [Core Concepts](concepts.md) - Understand how Egregora works
- [Configuration Guide](../guides/configuration.md) - Customize your setup

## Troubleshooting

### Python Version Issues

```bash
# Check your Python version
python --version

# If < 3.11, install a newer version
# On Ubuntu/Debian:
sudo apt install python3.11

# On macOS with Homebrew:
brew install python@3.11
```

### API Key Issues

```bash
# Test your API key
curl -H "x-goog-api-key: YOUR_KEY" \
  https://generativelanguage.googleapis.com/v1/models
```

If this fails, your API key may be invalid. Get a new one at [Google AI Studio](https://ai.google.dev/).

### Installation Errors

If you encounter errors during installation:

```bash
# Upgrade pip
pip install --upgrade pip

# Try installing with verbose output
pip install egregora -v
```

For more help, see the [Troubleshooting Guide](../guides/troubleshooting.md) or [open an issue](https://github.com/franklinbaldo/egregora/issues).
