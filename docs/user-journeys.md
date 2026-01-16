# 🎭 User Journeys

This document maps the key user journeys for Egregora, serving as a guide for the Curator persona to optimize the experience. It distinguishes between the **Creator** (the user running the software) and the **Reader** (the audience of the generated blog).

## 🛠️ The Creator's Journey

The Creator is the technical user who installs Egregora to transform their chat archives into a blog.

### 1. Discovery & Setup
**Goal:** Successfully install Egregora and verify the environment.
*   **Trigger:** User wants to archive a group chat or make it readable.
*   **Actions:**
    *   Installs `uv` (if not present).
    *   Installs Egregora: `uv tool install ...`
    *   Obtains and exports `GOOGLE_API_KEY`.
*   **Pain Points:** Python version mismatches, API key confusion, dependency conflicts.
*   **Success:** `egregora --help` runs without error.

### 2. The Genesis (Initialization)
**Goal:** Create the scaffolding for a new blog site.
*   **Actions:**
    *   Runs `egregora init ./my-blog`.
    *   Explores the generated directory structure.
*   **Expectation:** A clear, clean folder structure with configuration files ready to go.
*   **Success:** A functional site structure exists at the target path.

### 3. The Transformation (Ingestion & Writing)
**Goal:** Convert raw, chaotic chat logs into structured narratives.
*   **Actions:**
    *   Locates the WhatsApp export ZIP file.
    *   Runs `egregora write path/to/chat.zip --output-dir=.`.
    *   Monitors the CLI progress bars (Ingestion, Enrichment, Writing).
*   **Experience:** The user watches the "magic" happen. Progress feedback is critical here as the process can be slow.
*   **Pain Points:** Long wait times, unclear errors if the LLM fails, rate limiting.
*   **Success:** Markdown files appear in `docs/posts/`.

### 4. The Review & Refinement
**Goal:** Verify the quality of the output and tweak the voice.
*   **Actions:**
    *   Runs the local server: `mkdocs serve`.
    *   Reads the generated posts.
    *   Adjusts `.egregora/prompts/writer.jinja` or configuration in `.egregora.toml` to change the tone.
    *   Re-runs generation (optional).
*   **Success:** The Creator is satisfied with the narrative voice and layout.

---

## 👁️ The Reader's Journey

The Reader is the consumer of the content. Their experience is defined by the "Portal" vision—immersive, content-first, and polished.

### 1. The Arrival (Landing)
**Goal:** Immediately understand the context and vibe of the collective.
*   **Touchpoint:** Homepage (index).
*   **Experience:**
    *   Greeted by the "Portal" aesthetic (Dark mode, deep blues/golds).
    *   Clear site title and description explaining the source material (e.g., "The Archives of Group X").
    *   Recent posts or a "Start Here" guide are prominent.

### 2. Exploration (Navigation)
**Goal:** Find interesting conversations or specific topics.
*   **Actions:**
    *   Browses the timeline (Chronological).
    *   Uses the Search bar (Material for MkDocs instant search).
    *   Clicks on Tags (Topics extracted by AI).
*   **Success:** Seamless transition between posts; intuitive information architecture.

### 3. Immersion (Reading)
**Goal:** Read a post without distraction.
*   **Experience:**
    *   **Typography:** Readable, high-contrast text (Inter/Outfit).
    *   **Media:** Images and videos embedded naturally within the flow.
    *   **Context:** AI-generated summaries or "Context" boxes help explain inside jokes or referenced events.
*   **Success:** The Reader finishes the post and feels they were "part of the chat" without the noise.

### 4. Connection (Engagement)
**Goal:** Share or dig deeper.
*   **Actions:**
    *   Follows links to related posts (Internal linking).
    *   (Future) Subscribes via RSS.
*   **Success:** The Reader returns to the site.
