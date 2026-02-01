# WhatsApp to Blog Example

This guide walks you through transforming a WhatsApp chat export into a fully functional blog site using Egregora.

## Goal

Create a searchable, privacy-first blog site from a WhatsApp group chat history, complete with AI-generated summaries, tags, and author profiles.

## Prerequisites

*   **Egregora installed**: Follow the [Installation Guide](../getting-started/installation.md).
*   **Google API Key**: You need a key for Gemini. Get one [here](https://aistudio.google.com/app/apikey).
*   **WhatsApp Export**: A `.zip` file exported from a WhatsApp chat.

## Step 1: Export Chat from WhatsApp

1.  Open the WhatsApp chat you want to export on your phone.
2.  Tap the group name (iOS) or three dots > More (Android).
3.  Select **Export Chat**.
4.  Choose **Attach Media** (recommended for images) or **Without Media**.
5.  Save the resulting ZIP file to your computer (e.g., `family-chat.zip`).

## Step 2: Initialize Your Site

Run the `init` command to create the skeleton of your blog site.

```bash
egregora init my-family-blog
```

This creates a directory `my-family-blog` with the necessary configuration files.

## Step 3: Generate Content

Use the `write` command to process the chat export and generate blog posts.

```bash
# Set your API key first
export GOOGLE_API_KEY="your_api_key_here"

# Run the generation pipeline
egregora write family-chat.zip --output-dir my-family-blog
```

**What happens next?**
1.  **Ingestion**: Egregora reads the chat messages.
2.  **Windowing**: It groups messages into logical "windows".
3.  **Writing**: The AI (Gemini) reads each window and writes a blog post summary.
4.  **Enrichment**: It selects appropriate images from the export to include in the post.

*Note: This process may take a few minutes depending on the size of your chat.*

## Step 4: Preview Your Site

Once generation is complete, you can serve the site locally to view it.

Navigate into your site directory:

```bash
cd my-family-blog
```

Then run the preview server.

**Option A: Using `uv` (Recommended)**

```bash
uv tool run --with "mkdocs-material[imaging]" \
    --with pillow \
    --with cairosvg \
    --with mkdocs-blogging-plugin \
    --with mkdocs-macros-plugin \
    --with mkdocs-rss-plugin \
    --with mkdocs-glightbox \
    --with mkdocs-git-revision-date-localized-plugin \
    --with mkdocs-minify-plugin \
    mkdocs serve -f .egregora/mkdocs.yml
```

**Option B: If you have dependencies installed in your environment**

```bash
mkdocs serve -f .egregora/mkdocs.yml
```

Open your browser to `http://127.0.0.1:8000` to see your new blog!

## Customization

You can customize the site title, author names, and more by editing `.egregora/config.yml` in your site directory. See the [Configuration Guide](../getting-started/configuration.md) for details.
