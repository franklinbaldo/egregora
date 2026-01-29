# RFC 030: Egregora Symphony (The Living Oral History)

**Status:** Proposed
**Author:** Jules (Visionary)
**Date:** 2026-01-26

## 🔭 Problem Statement

Egregora currently reduces the vibrant, chaotic, and noisy reality of human conversation into static text and images. While the "Emotional Portraits" feature captures the *essence* of a person, it fails to capture their *presence*.

We assume memory is something you read. But for most of human history, memory was something you *heard*. Oral traditions, campfire stories, and radio dramas carry an emotional weight that text cannot replicate.

By limiting output to visual media (blogs), we:
1.  **Flatten Emotion:** Sarcasm, timing, and tone are lost.
2.  **Limit Accessibility:** We exclude those who learn by listening or have visual impairments.
3.  **Enforce Active Consumption:** You must sit and read. You cannot "experience" the memory while driving or cooking.

## 💡 Proposed Solution

**Egregora Symphony** is a multimodal engine that transforms the textual archive into an immersive auditory experience. It is not just a "screen reader" but a **Generative Audio Drama Engine**.

It consists of three layers:
1.  **The Scriptwriter (LLM):** Converts chat logs into a "Radio Play" script, adding stage directions, sound effects cues (SFX), and emotional markers based on the Contextual Memory and Author Profiles.
2.  **The Casting Director (Config):** Assigns distinct voice profiles (TTS) to each participant. These can be generic ("The Grumpy Old Man") or, with consent, cloned voices.
3.  **The Studio (Audio Engine):** Synthesizes speech, mixes in ambient background noise (e.g., "coffee shop noise" if the chat mentions meeting up), and produces a high-fidelity audio file.

## 💎 Value Proposition

*   **Emotional High-Fidelity:** Reclaiming the "lost signals" of conversation (tone, pacing).
*   **Passive Engagement:** Allowing users to "listen to their life" like a podcast.
*   **Deep Accessibility:** Making the archive accessible to the blind and screen-fatigued.

## ✅ BDD Acceptance Criteria

```gherkin
Feature: Generative Audio Drama
  As a community member
  I want to listen to a re-enactment of a past conversation
  So that I can relive the moment emotionally without reading

  Scenario: Generating a Drama from a tense argument
    Given a chat window with "High Conflict" sentiment
    And Author A has a "Aggressive" profile
    And Author B has a "Pacifist" profile
    When the Symphony Engine processes the window
    Then the generated script should include "[SFX: Tense music]" cues
    And Author A's voice should be rendered with fast pacing and high volume
    And Author B's voice should be rendered with slow pacing and soft volume
    And the output should be a single mixed MP3 file

  Scenario: Ambient Context Injection
    Given a chat window discussing "Camping Trip"
    When the Symphony Engine processes the window
    Then the background audio track should be "Nature/Fire Crackling"
    And the audio mix should duck the background noise during speech

  Scenario: Privacy-Preserving Voice Assignment
    Given an author who has opted out of Voice Cloning
    When the Symphony Engine assigns a voice
    Then a generic, non-identifiable voice actor (e.g., "Generic Male 1") should be used
    And the voice should NOT match their real biometric data
```

## 🛠️ Implementation Hints

*   **Scriptwriter:** Extend `WriterAgent` to output a structured script format (e.g., Fountain or JSON) instead of Markdown.
*   **Audio Engine:** Use a modular provider system (OpenAI TTS, ElevenLabs, or local Coqui TTS/Piper for privacy).
*   **Mixing:** Use `ffmpeg` or `pydub` to overlay TTS tracks onto ambient loops.
*   **Integration:** Add `audio` tag to the MkDocs template to embed the player.

## ⚠️ Risks

*   **Deepfake Ethics:** Cloning voices without explicit, cryptographic consent is a major risk. **Mitigation:** Default to generic "Character Archetype" voices, strictly opt-in for cloning.
*   **Cost/Latency:** High-quality TTS is expensive and slow. **Mitigation:** Batch processing at night; allow "Low-Fi" local generation.
*   **Hallucination:** The "Scriptwriter" might invent dialogue to bridge gaps. **Mitigation:** Strict grounding prompts; visual diff of script vs. original logs.
