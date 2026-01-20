# Getting Started with Egregora - Video Script

> **Duration:** 3-5 minutes
> **Style:** Screencast with voiceover
> **Tone:** Warm, friendly, slightly magical

---

## Scene 1: The Problem (0:00 - 0:30)

**Visual:** WhatsApp interface scrolling through thousands of messages

**Voiceover:**
> "You have years of conversations with the people you love. Inside these chats are memories, stories, and moments you want to preserve. But chat apps aren't built for this. Messages scroll away, important moments get buried, and there's no way to turn these conversations into something you can actually read and share."

**Visual:** Close WhatsApp, show Egregora logo

**Voiceover:**
> "Meet Egregora. It transforms your chat history into stories that remember."

---

## Scene 2: What Makes It Special (0:30 - 1:15)

**Visual:** Split screen showing generic summary vs Egregora post

**Left side (generic):**
```
The group discussed vacation plans.
```

**Right side (Egregora):**
```
Remember when we were torn between beach vs mountains?
After weeks of debating (Dad still advocating for historical sites),
we finally chose the coast. Everyone's excited...
```

**Voiceover:**
> "Egregora doesn't just summarize. It creates connected narratives that feel like a continuing story. Posts reference previous discussions,

 automatically."

**Visual:** Show "Top Posts" section appearing

**Voiceover:**
> "It discovers your best memories and surfaces them automatically. No more scrolling through hundreds of posts to find the gems."

**Visual:** Show profile of "Dad"

**Voiceover:**
> "And it creates loving portraits of each person—capturing their personality, quirks, and voice. Not statistics. Storytelling."

**Visual:** Text overlay: "🧠 Contextual Memory | 🏆 Content Discovery | 💝 Author Profiles"

**Voiceover:**
> "All three features work automatically. Zero configuration. That's the magic."

---

## Scene 3: Installation (1:15 - 1:45)

**Visual:** Terminal window

**Voiceover:**
> "Let me show you how easy this is. First, install Egregora with one command:"

**Type:**
```bash
uv tool install git+https://github.com/franklinbaldo/egregora
```

**Wait for installation to complete**

**Voiceover:**
> "You'll also need a Google Gemini API key. It's free—just sign up at ai.google.dev."

**Type:**
```bash
export GOOGLE_API_KEY="your-api-key-here"
```

**Voiceover:**
> "And that's it. You're ready."

---

## Scene 4: The Magic (1:45 - 3:30)

**Visual:** Terminal, starting fresh

**Voiceover:**
> "Now let's create some magic. I have a WhatsApp export from my family group—three years of conversations, about 2,000 messages."

**Show file:** `family-chat.zip`

**Voiceover:**
> "First, initialize a new blog:"

**Type:**
```bash
egregora init my-family-blog
cd my-family-blog
```

**Visual:** Directory structure appears

**Voiceover:**
> "This creates the structure for your blog. Now, transform the chat:"

**Type:**
```bash
egregora write ../family-chat.zip
```

**Visual:** Progress indicators

**Voiceover (while processing):**
> "Watch what happens. Egregora is building a vector index of all the conversations—that's the contextual memory. It's analyzing each person's messages to create profiles. And it's generating blog posts that reference previous discussions."

**Visual:** Processing completes

**Voiceover:**
> "Done. Let's see what we got."

**Type:**
```bash
mkdocs serve -f .egregora/mkdocs.yml
```

**Visual:** Browser opens to localhost:8000

---

## Scene 5: The Reveal (3:30 - 4:30)

**Visual:** Scroll through the blog slowly

**Voiceover:**
> "Here's the magic. Look at this post from July—it references our March discussion about vacation. 'Remember when we were torn between beach vs mountains?' It REMEMBERED."

**Click "Top Posts"**

**Voiceover:**
> "And here's the Top Posts section—automatically created. 'The Baby Announcement', 'Dad's 70th Birthday Planning', 'Our Beach vs Mountains Debate'. These ARE our best memories!"

**Click on "Profiles"**

**Voiceover:**
> "And look at this. Profiles of everyone in the chat. Let me click on Dad."

**Read a snippet:**
> "Dad is the family's tech support, history buff, and terrible joke teller. He posts mainly on weekday evenings, always asks about everyone's day, and has an uncanny ability to derail any conversation into World War II trivia..."

**Visual:** Pause emotionally

**Voiceover (softer):**
> "This IS my dad. Egregora captured him perfectly."

---

## Scene 6: The Key Points (4:30 - 5:00)

**Visual:** Recap screen with key points

**Text on screen:**
- ✅ One command: `egregora write chat.zip`
- ✨ Posts that reference each other (Contextual Memory)
- 🏆 Best memories automatically surfaced (Content Discovery)
- 💝 Loving portraits of people (Author Profiles)
- 🔒 Runs locally—your data stays private
- 😊 Zero configuration required

**Voiceover:**
> "That's Egregora. One command. Five minutes. Stories that remember. Whether it's family memories, team knowledge, or research data—Egregora turns your conversations into something magical."

---

## Scene 7: Call to Action (5:00 - 5:15)

**Visual:** Egregora homepage/docs

**Text on screen:**
```
Get Started:
docs.egregora.dev

GitHub:
github.com/franklinbaldo/egregora
```

**Voiceover:**
> "Ready to transform your conversations? Visit the docs to get started. Your stories are waiting."

**Visual:** Fade to Egregora logo with tagline

**Text:** "Egregora - Turn your conversations into stories that remember"

---

## Production Notes

### Screen Recording Setup
- **Resolution:** 1920x1080
- **Terminal:** Use a clean theme (e.g., Dracula, Solarized Dark)
- **Font size:** Large enough to read (18-20pt)
- **Browser:** Chrome/Firefox with clean profile (no extensions visible)

### Timing
- Keep processing steps visible but use 2x speed if needed
- Show real output, but pre-select the chat export to save time
- Have the API key already set (don't show real key on screen)

### Visual Effects
- Use gentle zoom-ins for key moments (e.g., Dad's profile)
- Highlight cursor for important clicks
- Add subtle transitions between scenes
- Use callout boxes for key concepts

### Audio
- Warm, conversational tone (not overly formal)
- Background music: Subtle, ambient (very low volume)
- Pause slightly after emotional moments (Dad's profile)
- Emphasize the three magical features

### Accessibility
- Include captions
- Use high contrast themes
- Ensure all text is readable at 720p

---

## Alternative Version: 60-Second Teaser

For social media, create a 60-second version:

**0-10s:** The problem (chat scrolling)
**10-20s:** The solution (show terminal)
**20-40s:** The magic (show blog with Top Posts)
**40-50s:** The emotion (Dad's profile snippet)
**50-60s:** CTA (docs link)

---

## B-Roll Footage Ideas

If creating a more produced version:
- Person smiling while reading blog on phone
- Family members looking at old photos
- WhatsApp notification sound
- Calendar flipping through months/years
- Someone getting emotional reading a profile

---

*This script demonstrates Egregora's value in under 5 minutes while showing real usage. The emotional beat (Dad's profile) is key—this is where viewers will share the video.*
