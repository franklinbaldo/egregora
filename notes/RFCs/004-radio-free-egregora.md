# RFC: Radio Free Egregora (The Audio-First Archive)
**Status:** Moonshot Proposal
**Date:** 2025-05-28
**Disruption Level:** High (Modality Shift: Text -> Audio)

## 1. The Vision

You are driving to work. You missed yesterday's explosive debate in the group chat because you were... well, working. 200 messages is too much to read.

You say: *"Hey Siri, play the Group Chat."*

The car speakers crackle to life. A smooth, synthesized DJ voice—the **Egregora Host**—fades in over a low-fi hip-hop beat.

*"Good morning, crew. It's Tuesday, October 24th. The vibe today was... chaotic. Alice started a war about tab-vs-space indentation, and I think Bob might have accidentally quit his job? Let's get into it."*

Instead of reading a summary, you *hear* it.
And not just the host. When the Host quotes Alice, a synthesized voice *sounding like Alice* (but safe/anonymized) delivers the line with the appropriate sass. When Bob panic-messages, you hear the urgency.

It’s a 5-minute, highly produced "Morning Radio" segment, generated entirely from your Signal/WhatsApp logs. It turns the "chore" of catching up into entertainment.

## 2. The Broken Assumption
> "We currently assume that the output of a text chat must be **text**, but this restricts consumption to active reading."

Reading requires 100% visual attention. It competes with work, driving, and gaming.
Audio is **passive**. It accompanies you.
By outputting only static text sites, we are ignoring the dominant media consumption habit of the modern era: **The Podcast / Audiobook**.

We assume `Entry -> Markdown`.
We should assume `Entry -> Experience`.

## 3. The Mechanics (High Level)

### Input
*   **The Stream:** Standard `Entry` objects (text).
*   **Voice Profiles:** A new metadata field in `profiles/*.md`.
    *   `voice_id`: (e.g., "elevenlabs-adam", "openai-alloy").
    *   `style`: (e.g., "sarcastic", "fast-talker", "monotone").

### Processing
The pipeline forks at the Output layer. We introduce the **Studio Agent**.

1.  **The Scriptwriter (LLM):**
    *   Takes the daily cluster/summary.
    *   Writes a *Radio Script*. It adds cues: `[Sound Effect: Gavel banging]`, `[Host: whispering]`.
    *   It structures the narrative: Intro -> The "A" Plot (Main Drama) -> The "B" Plot (Side Jokes) -> Outro.

2.  **The Director (Logic):**
    *   Parses the script.
    *   Assigns voices. (Host = Default Voice, Alice = Alice's Voice Profile).
    *   Calculates timing/pacing.

3.  **The Synthesizer (TTS API):**
    *   Calls a high-quality TTS provider (ElevenLabs / OpenAI Audio API).
    *   Generates individual clips.
    *   Mixes them with background music (royalty-free loop) using `ffmpeg`.

### Output
*   **Artifact:** `daily-briefing-2025-10-24.mp3`.
*   **Distribution:** A standard RSS Feed (`podcast.xml`) generated alongside the Atom feed.
*   **Integration:** The MkDocs site embeds the audio player at the top of the daily post ("Listen to this Summary").

## 4. The Value Proposition

*   **Zero-Friction Consumption:** Users don't need to "find time to read." They listen while doing dishes. Usage skyrockets.
*   **Emotional High-Fidelity:** Text often loses tone. Audio restores sarcasm, excitement, and hesitation (via LLM-directed prosody).
*   **Accessibility:** Makes the archive accessible to users with visual impairments or reading difficulties.
*   **The "Magic" Factor:** Hearing your friends' simulated voices debating a trivial topic is surreal, hilarious, and deeply engaging. It feels like *science fiction*.
