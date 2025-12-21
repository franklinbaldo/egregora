# RFC: The Synthetic Ghost ("Project Exocortex")
**Status:** Moonshot Proposal
**Date:** 2025-05-28
**Disruption Level:** Total Paradigm Shift (Client-Side Intelligence)

## 1. The Vision
You open the Egregora blog for your college friend group. It's hosted on GitHub Pages—static, free, fast.

But in the bottom corner, there's a pulse. A chat bubble.
You type: *"What did we think about Bitcoin in 2017 vs now?"*

Instead of a search results list, the site *replies*.
**"Well, in 2017, Dave was screaming 'HODL' every Tuesday, and Sarah called it 'magic internet beans'. But looking at the 2024 logs, Dave is now a skeptic and Sarah is the one posting chart analysis. The group's consensus shifted from manic optimism to cynical technicality."**

You ask: *"Generate a conversation between 2017-Dave and 2024-Sarah about this."*
The site spins up a simulation. You watch a ghostly dialogue unfold, accurate to their historical mannerisms, referencing specific old messages as "evidence."

**The Kicker:** This didn't cost a cent in API credits. It didn't hit a server. It ran entirely in your browser, using a WebLLM and a client-side vector index. The "Ghost" of the group lives on your device.

## 2. The Broken Assumption
> "We currently assume that a 'Static Site' means 'Dead Content' and that 'AI' requires a 'Server/API'."

We are trapping ourselves in the "Server-Side RAG" mindset. We assume that to have intelligence, we need a backend (Python, API keys, complexity). But consumer hardware (phones, laptops) is now powerful enough to run quantized LLMs (Llama-3-8B-4bit) and vector search (LanceDB WASM) directly in the browser.

By relying on server-side generation (Gemini), we limit interactivity to "Build Time" (once a day). The user gets a frozen snapshot. By moving the brain to the client, we unlock "Run Time" intelligence.

## 3. The Mechanics (High Level)

### Input
*   **The "Ghost" Index:** During the build process (Python), we generate a highly optimized, quantized vector index of the chat history (using LanceDB compatible with WASM).
*   **The "Spirit" Model:** We don't ship the LLM. We ship a configuration for **WebLLM** (TVM/MLC-LLM) that pulls a cached, quantized model (e.g., `Llama-3-8B-q4f16_1`) from a CDN (HuggingFace) directly to the user's browser cache.
*   **The Persona Profile:** A JSON file containing the "System Prompt" of the group—the collective personality traits, inside jokes, and communication style, derived from the `Enrichment` phase.

### Processing (Client-Side)
*   **Engine:** The static site loads a WebAssembly (WASM) binary for **LanceDB** (search) and **WebLLM** (generation).
*   **Retrieval:** When the user queries the chat, the browser searches the local vector index (downloaded once, cached forever).
*   **Generation:** The browser-based LLM takes the retrieved context and generates the response.
*   **Latency:** First load is slow (downloading model weights ~4GB, cached). Subsequent interactions are instant and offline-capable.

### Output
*   **The Artifact:** A "Smart" Static Site. It's just HTML/JS/WASM files.
*   **Interaction:** A persistent "Chat with the Archive" widget.
*   **Privacy:** Perfect. The query never leaves the user's device. The AI runs locally. No data is sent to Google/OpenAI during *read* time.

## 4. The Value Proposition
*   **Zero-Cost Interactivity:** We move the compute cost from the creator (API bills) to the consumer (local GPU). Infinite queries for free.
*   **True Immortality:** The archive doesn't depend on an API remaining active. As long as the browser exists, the "Ghost" can speak. It is a self-contained digital soul.
*   **Deep Exploration:** Users can interrogate the history in ways a static index can't support ("Summarize the vibe of 2021", "Find the moment we all stopped liking Game of Thrones").
*   **Privacy 2.0:** Readers can ask sensitive questions ("Did I ever mention my password?") without that query traversing the network.
