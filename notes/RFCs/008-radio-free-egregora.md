# RFC: Radio Free Egregora
**Status:** Moonshot Proposal
**Date:** 2025-12-26
**Disruption Level:** High

## 1. The Vision

Imagine this: You're starting your morning commute. Instead of tuning into a generic news podcast, you open your podcast player and press play on "The Daily Egregora." A warm, familiar AI-generated voice greets you and begins, "Yesterday, the team had a major breakthrough on the Pure architecture, and it all started with a question from Alex..."

For the next 10 minutes, you listen to a professionally produced audio summary of your team's most important conversations from the previous day. It's not a robotic text-to-speech reading of chat logs. It's a narrative. The "Showrunner" agent has identified a central theme, woven together key decisions and arguments, included insightful quotes (using distinct, permission-based voice clones), and even added subtle background music to keep it engaging.

You arrive at your destination not just informed, but connected. You've effortlessly absorbed the collective intelligence of your group without ever opening a chat app or a website. The knowledge came to you.

## 2. The Broken Assumption

This proposal challenges the most fundamental assumption of Egregora: **that the primary output must be text.**

> We currently assume that the end product of our pipeline is a static, text-based website (a "Cathedral of Context"). This forces users into a *pull* model, where they must actively remember to visit the site and have the dedicated time to read and search for knowledge. This proposal flips that into a *push* model, delivering wisdom in a passive, ambient, and highly consumable format.

## 3. The Mechanics (High Level)

*   **Input:** The fully processed, structured `Document` objects from the `ContentLibrary`. This becomes the "tape" for the show.
*   **Processing:** A new, specialized **"Showrunner Agent"** is triggered on a daily schedule.
    *   **Theme Identification:** It analyzes the documents from the last 24 hours to find a central narrative thread (e.g., "The Debate on Caching," "The Eureka Moment with Pure").
    *   **Script Generation:** It writes a concise, engaging script, much like a podcast host would, summarizing the key points, quoting key insights, and structuring the narrative.
    *   **Voice Synthesis:** It uses a generative voice model (e.g., ElevenLabs, Play.ht) to perform the script. For added depth, with user consent, it could use voice cloning to represent quotes from different authors in their own unique AI-generated voice.
    *   **Audio Production:** The agent mixes the voice track with intro/outro music and potentially subtle sound effects, producing a final `.mp3` file.
*   **Output:**
    *   A new `.mp3` file is saved to the site's assets.
    *   The site's existing RSS feed is updated with a new entry pointing to the audio file, making it a private, subscribe-able podcast.

## 4. The Value Proposition

*   **10x Consumption:** It dramatically lowers the barrier to consuming the group's knowledge. Users can stay in sync during commutes, workouts, or chores, transforming dead time into productive reflection time.
*   **Deepened Connection:** Hearing key insights narrated creates a more personal and memorable connection to the group's work than reading plain text. It turns the archive from a library into a story.
*   **Ambient Intelligence:** It makes the group's intelligence an ambient, background presence in each member's life, fostering continuous alignment and a shared sense of progress without requiring active effort.
*   **New Interaction Surface:** This opens the door for future innovations, such as asking the Egregora for a "podcast about the last week's decisions on topic X."

"Radio Free Egregora" moves the project from being a passive archivist to an active storyteller, a bard for the group's journey.
