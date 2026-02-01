# Tutorial: From WhatsApp to Blog

Transform your group chat history into a searchable, story-driven blog site in minutes.

In this tutorial, we will take a WhatsApp export (a simple ZIP file) and use Egregora to generate a beautiful static site preserving your memories.

## Scenario

Imagine you have a WhatsApp group called **"Family Trip 2024"**. It has thousands of messages, photos, and inside jokes. You want to preserve these memories in a format better than scrolling through endless text.

**Goal:** Create a private website titled "The Smith Family Adventures" with:
*   Daily summaries of the trip.
*   Profiles for each family member.
*   A searchable archive of all conversations.

---

## Prerequisites

1.  **Python 3.12+** installed.
2.  **uv** installed (Egregora's package manager).
3.  A **Google Gemini API Key**.
4.  A **WhatsApp Chat Export** (ZIP file).

!!! note "Need an API Key?"
    You can get a free API key from [Google AI Studio](https://aistudio.google.com/app/apikey). Egregora works great with the free tier!

---

## Step 1: Export Your Chat

First, we need the raw data.

1.  Open the WhatsApp group on your phone.
2.  Tap the group name at the top.
3.  Scroll down and select **Export Chat**.
4.  Choose **Without Media** (for this tutorial).
    *   *Note: Egregora supports media, but "text-only" is faster for your first run.*
5.  Save the resulting ZIP file to your computer (e.g., `Downloads/WhatsApp Chat with Family.zip`).

---

## Step 2: Initialize Your Site

Open your terminal and create a new Egregora site.

```bash
# Install Egregora (if you haven't already)
uv tool install git+https://github.com/franklinbaldo/egregora

# Create a new site directory
egregora init family-memories

# Enter the directory
cd family-memories
```

You will see a structure like this:
```
family-memories/
├── egregora.toml    # Configuration file
├── .egregora/       # Database and cache (hidden)
└── ...
```

---

## Step 3: Configure the Site

Open `egregora.toml` in your favorite text editor. We'll customize it for our scenario.

Change the `[site]` section:

```toml
[site]
name = "The Smith Family Adventures"
description = "Our trip to Italy in Summer 2024"
author = "Egregora"
url = "https://example.com"  # You can change this later
```

And ensuring the `[models]` section uses a model you have access to (defaults are usually fine):

```toml
[models]
writer = "google-gla:gemini-2.0-flash"  # Fast and efficient
```

---

## Step 4: Set Your API Key

Egregora needs your API key to use the AI model.

**Mac / Linux:**
```bash
export GOOGLE_API_KEY="your-key-starts-with-AIza..."
```

**Windows (PowerShell):**
```powershell
$Env:GOOGLE_API_KEY = "your-key-starts-with-AIza..."
```

---

## Step 5: Generate the Stories

Now, run the `write` command. Point it to your ZIP file.

```bash
egregora write path/to/WhatsApp\ Chat\ with\ Family.zip --output-dir .
```

!!! tip "Tip"
    You can drag and drop the ZIP file into the terminal window to auto-complete the path.

**What happens next?**
1.  **Ingestion:** Egregora reads the ZIP and extracts messages.
2.  **Windowing:** It groups messages into "windows" (e.g., days).
3.  **Enrichment:** It finds links and creates context.
4.  **Writing:** The AI reads each window and writes a blog post summarizing the events, emotions, and key discussions.
5.  **Profiling:** It analyzes the participants and generates personality profiles.

*This process might take 5-10 minutes depending on the chat size.*

---

## Step 6: View Your Site

Once the command finishes, your site is ready locally.

```bash
# Start the preview server
uv tool run --from "git+https://github.com/franklinbaldo/egregora[mkdocs]" mkdocs serve -f .egregora/mkdocs.yml
```

Open **[http://localhost:8000](http://localhost:8000)** in your browser.

### What to Explore

*   **The Feed:** Scroll through chronological posts summarizing your chat.
*   **Profiles:** Click on "Authors" or names to see AI-generated profiles of your family members.
*   **Search:** Use the search bar to find specific memories (e.g., "pizza", "lost passport").

---

## Step 7: Deployment (Optional)

To share this with your family, you can host it for free on GitHub Pages.

1.  Create a new repository on GitHub.
2.  Push your `family-memories` folder to it.
3.  Enable GitHub Pages in the repository settings.
4.  Run the deploy command:

```bash
uv tool run --from "git+https://github.com/franklinbaldo/egregora[mkdocs]" mkdocs gh-deploy -f .egregora/mkdocs.yml
```

Your site will be live at `https://<your-username>.github.io/<repo-name>/`.

---

## Troubleshooting

*   **"Quota exceeded":** You hit the API rate limit. Egregora retries automatically, but you can also wait a minute and run the command again (it resumes where it left off).
*   **"No posts generated":** Check if your date range in `egregora.toml` matches the dates in your chat.

## Next Steps

*   [Customize the Writer](../reference/api/config/settings.md): Change the prompt to write in a different style (e.g., "Pirate", "Formal").
*   [Enrichment](../getting-started/configuration.md#feature-flags): Enable link previews and media descriptions.
