# Quick Start

**Turn your chats into stories in 5 minutes.**

This guide is designed for everyone—you don't need to be a programmer to use it.

## Prerequisites

Before we start, you will need:
1.  **Python 3.12+** installed on your computer.
2.  **uv** (a tool to run Egregora).
3.  A **Google Gemini API Key** (it's free!).

[See Glossary](../glossary.md) if any of these terms are new to you.

---

## Step 1: Install Egregora

Open your **Terminal** (Mac) or **PowerShell** (Windows) and copy-paste this command:

```bash
uv tool install git+https://github.com/franklinbaldo/egregora
```

## Step 2: Create Your Site

Now, let's create a folder for your new blog. Copy these commands:

```bash
egregora init my-blog
cd my-blog
```

This creates a folder named `my-blog` with everything you need.

## Step 3: Export Your Chat

1.  Open **WhatsApp** on your phone.
2.  Go to the chat you want to save.
3.  Tap the name of the person/group at the top.
4.  Scroll down to **Export Chat**.
5.  Choose **Without Media** (this is faster and safer for now).
6.  Save the ZIP file to your computer.

## Step 4: Add Your Magic Key

You need to tell Egregora your API Key so it can write stories.

**Mac / Linux:**
```bash
export GOOGLE_API_KEY="paste-your-key-here"
```

**Windows (PowerShell):**
```powershell
$Env:GOOGLE_API_KEY = "paste-your-key-here"
```

*(Replace `paste-your-key-here` with the actual key from Google)*

## Step 5: Make Magic!

This is where the magic happens. Run this command:

```bash
egregora write path/to/your/whatsapp-export.zip --output-dir=.
```
*(Tip: You can drag and drop the ZIP file into the terminal window to get the path)*

Egregora will now:
*   ✨ Read your chat history.
*   🧠 Find the most important memories.
*   💝 Write stories and create profiles for everyone.

**Grab a coffee! ☕** This might take a few minutes depending on how long your chat is.

## Step 6: See Your Stories

Once it's done, you can see your beautiful new site. Run this command:

```bash
uv tool run --from "git+https://github.com/franklinbaldo/egregora[mkdocs]" mkdocs serve -f .egregora/mkdocs.yml
```

Now open your web browser and go to: **[http://localhost:8000](http://localhost:8000)**

🎉 **Congratulations! You have preserved your memories.**

---

<details>
<summary>🔧 Advanced Options & Troubleshooting (Click to Expand)</summary>

## Common Options

```bash
# Daily windowing (default)
egregora write export.zip --step-size=1 --step-unit=days

# Enable URL/media enrichment
egregora write export.zip --enable-enrichment

# Custom date range
egregora write export.zip --from-date=2025-01-01 --to-date=2025-01-31

# Different model
egregora write export.zip --model=google-gla:gemini-pro-latest

# Incremental processing (resume previous run)
egregora write export.zip --resume

# Invalidate cache tiers
egregora write export.zip --refresh=writer  # Regenerate posts
egregora write export.zip --refresh=all     # Full rebuild
```

## Troubleshooting

### "No posts were generated"
Check that:
1. Your chat has enough messages.
2. The date range includes your messages.

### Rate Limiting
If you hit API rate limits, Egregora will automatically retry.

### LanceDB Permission Issues
In restricted environments, ensure `.egregora/lancedb/` is writable:
```bash
chmod -R u+w .egregora/lancedb/
```

</details>

## Next Steps

*   [Customize your site](../configuration.md)
*   [Learn about the Magic Features](../index.md#what-makes-egregora-magical)
