# User Personas

This document defines the three primary user personas for Egregora. Understanding these personas helps guide product decisions, feature prioritization, and communication strategy.

---

## Overview

| Persona | Priority | % of Users | Tech Level | Primary Goal |
|---------|----------|------------|------------|--------------|
| Maya - Memory Keeper | Primary | 60% | Non-technical | Preserve family/friend memories |
| Tim - Team Lead | Secondary | 30% | Technical | Document team knowledge |
| Rachel - Researcher | Tertiary | 10% | Very Technical | Analyze conversation data |

---

## 👩‍👧‍👦 Maya - Memory Keeper (Primary Persona)

### Demographics
- **Age:** 28-55
- **Occupation:** Various (teacher, designer, parent, manager)
- **Tech Comfort:** Can follow tutorials, won't debug errors
- **Platform:** Mainly uses WhatsApp for family/friend groups

### Background Story
> "I have 5 years of family WhatsApp messages. My dad passed away last year, and I want to preserve his messages—his jokes, his advice, the way he talked. I also want to create something I can share with my kids someday, showing them what our family conversations were like."

### Goals
- **Primary:** Preserve meaningful conversations with loved ones
- **Secondary:** Share curated memories with family members
- **Tertiary:** Create a readable archive for future generations

### Pain Points
- **Too much data:** "I have thousands of messages. I can't read them all."
- **Lost in noise:** "95% is 'good morning' and logistics. I want the meaningful stuff."
- **No tech skills:** "I can't code. I need something that just works."
- **Privacy concerns:** "These are private family conversations. I don't want them on someone's server."

### What Success Looks Like
✅ Runs one command, gets a beautiful blog
✅ Posts feel connected like a story, not isolated
✅ "Top Memories" section shows the gems
✅ Dad's profile captures his personality perfectly → *cries happy tears* 😭
✅ Can share the blog privately with family
✅ Never had to edit a config file

### How Egregora Helps
- **🧠 Contextual Memory:** Posts reference previous discussions → feels like a continuing story
- **🏆 Content Discovery:** Automatically surfaces "The Baby Announcement" and "Dad's Wisdom"
- **💝 Author Profiles:** Captures Dad's jokes, Mom's encouragement, Sister's sarcasm
- **🔒 Privacy:** Runs locally, can anonymize names
- **😊 Zero Config:** Just works out of the box

### Quote
> "I thought I'd have to spend weeks organizing these messages. Instead, I ran one command and got a blog that made me cry. It captured my dad PERFECTLY. This is exactly what I needed."

### User Journey
1. Hears about Egregora from a friend or blog post
2. Downloads WhatsApp export (with guidance)
3. Installs Egregora (follows simple instructions)
4. Runs `egregora write chat.zip`
5. Previews blog, discovers Dad's profile
6. Shares top posts with family
7. Tells everyone about it 💕

---

## 👨‍💼 Tim - Team Lead (Secondary Persona)

### Demographics
- **Age:** 30-45
- **Occupation:** Product Manager, Engineering Lead, Team Lead
- **Tech Comfort:** Comfortable with CLI, git, Docker, YAML configs
- **Platform:** Primarily uses Slack for team communication

### Background Story
> "My engineering team has 2 years of Slack history across 15 channels. We make important technical decisions in chat, but they get lost. New team members ask questions we've answered before. I need a searchable knowledge base that captures our actual discussions, not just formal docs."

### Goals
- **Primary:** Create searchable knowledge base from team chats
- **Secondary:** Onboard new team members faster
- **Tertiary:** Surface best technical discussions and decisions

### Pain Points
- **Decisions get lost:** "We discussed why we chose PostgreSQL in March. Where is that?"
- **Repetitive questions:** "New hires ask the same questions every time."
- **Slack search sucks:** "I can find exact keywords but not concepts."
- **No narrative:** "Discussions span weeks. I need the full story."

### What Success Looks Like
✅ All Slack channels converted to searchable blog
✅ "Top Posts" shows key technical decisions
✅ Posts reference previous discussions (e.g., "Building on our database choice in March...")
✅ New hires can read "The Great Framework Debate" in 10 minutes
✅ Team profiles show who knows what
✅ Can customize to fit team workflow

### How Egregora Helps
- **🧠 Contextual Memory:** Discussions reference previous decisions → full narrative
- **🏆 Content Discovery:** Surfaces "Why We Chose X" and "The Y Decision"
- **💝 Author Profiles:** Shows expertise areas per team member
- **⚙️ Configurable:** Can customize models, prompts, windowing
- **🔍 Searchable:** Material for MkDocs has excellent search

### Quote
> "We've documented more of our technical decision-making in one afternoon than in the past 2 years of trying to maintain a wiki. And the ranking feature automatically highlighted our most important discussions."

### User Journey
1. Hears about Egregora from Hacker News or colleague
2. Tries demo on personal WhatsApp first
3. Exports team Slack channel
4. Runs Egregora, gets blog
5. Shares with team, gets feedback
6. Customizes config for team needs
7. Sets up automated exports monthly
8. Becomes internal advocate

---

## 👩‍🔬 Rachel - Researcher (Tertiary Persona)

### Demographics
- **Age:** 25-40
- **Occupation:** Academic researcher, UX researcher, data analyst
- **Tech Comfort:** Can code in Python, modify source code, use Jupyter
- **Platform:** Interview transcripts, Discord communities, specialized chat data

### Goals
- **Primary:** Analyze conversation patterns and themes
- **Secondary:** Identify key contributors and collaboration patterns
- **Tertiary:** Export structured data for further analysis

### Pain Points
- **Manual coding is tedious:** "I spend weeks coding interview transcripts."
- **Need structure:** "I need themes, not just summaries."
- **Want rankings:** "Which conversations were most informative?"
- **Export data:** "I need CSV/JSON exports for R/Python analysis."

### What Success Looks Like
✅ Upload interview transcripts, get thematic posts
✅ Author profiles identify participant communication patterns
✅ Ranking data exported to CSV for statistical analysis
✅ Can disable features she doesn't need
✅ Can customize profiling focus (e.g., technical vs emotional contributions)
✅ Can extend with custom code

### How Egregora Helps
- **🧠 Contextual Memory:** Thematic connections across interviews
- **🏆 Content Discovery:** Identifies most substantive conversations
- **💝 Author Profiles:** Analyzes participant patterns and styles
- **📊 Exportable:** Rankings and metadata export to CSV
- **🔧 Customizable:** Can modify code, add custom adapters

### Quote
> "I was prepared to spend 3 weeks manually coding these transcripts. Egregora gave me thematic analysis and participant profiles in 30 minutes. I can focus on interpretation, not data wrangling."

### User Journey
1. Finds Egregora via academic Twitter or research tool list
2. Tests on sample interview data
3. Exports ranking data for validation
4. Compares Egregora's themes with manual coding
5. Integrates into research workflow
6. Publishes paper mentioning the tool
7. Contributes code back to project

---

## Design Implications

### For Maya (Primary)
- ✅ **Zero configuration must work perfectly**
- ✅ Clear error messages in plain language
- ✅ Privacy emphasized in all docs
- ✅ Emotional value in marketing
- ✅ Hand-holding in tutorials
- ❌ Don't assume tech knowledge
- ❌ Don't expose complexity

### For Tim (Secondary)
- ✅ Good defaults, but allow customization
- ✅ Documentation for power user features
- ✅ CLI-first design
- ✅ Integration examples (CI/CD, automation)
- ❌ Don't make config required
- ❌ Don't sacrifice defaults for flexibility

### For Rachel (Tertiary)
- ✅ Export functionality
- ✅ Extensibility points (adapters, protocols)
- ✅ Detailed technical docs
- ✅ Jupyter notebook examples
- ❌ Don't prioritize over Maya/Tim
- ❌ Don't complicate UX for niche needs

---

## Feature Prioritization Matrix

| Feature | Maya | Tim | Rachel | Priority |
|---------|------|-----|--------|----------|
| Zero-config transformation | ⭐⭐⭐ | ⭐⭐ | ⭐ | **P0** |
| Contextual Memory (RAG) | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | **P0** |
| Content Discovery (Ranking) | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | **P0** |
| Author Profiles | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | **P0** |
| Privacy controls | ⭐⭐⭐ | ⭐ | ⭐⭐ | **P0** |
| Beautiful output | ⭐⭐⭐ | ⭐⭐ | ⭐ | **P1** |
| Config customization | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | **P1** |
| Slack adapter | ⭐ | ⭐⭐⭐ | ⭐ | **P2** |
| Data export (CSV/JSON) | ⭐ | ⭐⭐ | ⭐⭐⭐ | **P2** |
| Code extensibility | ⭐ | ⭐⭐ | ⭐⭐⭐ | **P3** |

**Legend:** ⭐⭐⭐ = Critical, ⭐⭐ = Important, ⭐ = Nice-to-have

---

## Product Positioning by Persona

### For Maya
> "Turn your family chats into stories you'll treasure forever."

**Emphasis:** Emotion, memories, love, preservation

### For Tim
> "Your team's knowledge base, generated from Slack—automatically."

**Emphasis:** Knowledge management, efficiency, searchability

### For Rachel
> "Conversation analysis with AI—themes, patterns, and insights in minutes."

**Emphasis:** Research utility, analysis, data export

---

## Success Metrics by Persona

### Maya
- ✅ Completes first blog without asking for help
- ✅ Shares blog with family members
- ✅ Reports emotional response ("I cried reading Dad's profile")
- ✅ Never opens config file

### Tim
- ✅ Integrates into team workflow
- ✅ Team members reference the blog weekly
- ✅ New hires use it for onboarding
- ✅ Customizes for team needs

### Rachel
- ✅ Uses in published research
- ✅ Exports data for analysis
- ✅ Compares favorably to manual coding
- ✅ Contributes back to project

---

*These personas guide all product decisions. When in doubt, ask: "What would Maya do?"*
