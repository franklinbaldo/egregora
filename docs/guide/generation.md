# Content Generation

Egregora's AI agents generate rich, contextual content from your personal knowledge graph through intelligent prompting and generation techniques.

## Writer Agent

The Writer Agent is responsible for creating the final output content:

### Core Responsibilities

- **Content Creation**: Generates summaries, journals, and documentation
- **Style Consistency**: Maintains consistent tone and style across output
- **Context Understanding**: Uses RAG to incorporate relevant information
- **Structural Organization**: Organizes information into coherent sections

### Generation Process

1. **Context Retrieval**: Fetches relevant information from your knowledge graph
2. **Prompt Construction**: Builds prompts with appropriate context and instructions
3. **Content Generation**: Uses LLMs to create the actual content
4. **Post-Processing**: Formats and structures the generated content

## Reader Agent

The Reader Agent processes and interprets your conversational data:

### Core Responsibilities

- **Data Interpretation**: Understands the meaning and context of conversations
- **Pattern Recognition**: Identifies trends, themes, and anomalies
- **Metadata Extraction**: Pulls out relevant information (topics, sentiment, etc.)
- **Quality Assessment**: Evaluates the richness and relevance of content

## Prompt Engineering

Egregora uses sophisticated prompt engineering for high-quality output:

### Contextual Prompts

Prompts include relevant context from your knowledge graph:

```
You are analyzing conversations between these anonymized participants:
- ANON_PERSON_1: Active participant, often initiates discussions
- ANON_PERSON_2: Listener, provides thoughtful responses

Recent context: [retrieved relevant conversations]
Current topic: [specific topic to focus on]
```

### Role-Based Instructions

Clear roles for consistent behavior:

```
As a personal knowledge curator, you will:
- Maintain a reflective, insightful tone
- Focus on meaningful insights rather than mundane details
- Preserve privacy by only including anonymized references
- Organize information chronologically and thematically
```

## Generation Modes

### Journal Mode

Creates personal journal entries from your conversations:

- **Daily Reflections**: Summarizes daily conversations and activities
- **Weekly Reviews**: Captures broader themes and progress
- **Thematic Journals**: Focuses on specific topics or relationships over time

### Documentation Mode

Generates structured documentation:

- **Relationship Documentation**: Chronicles connections with important people
- **Project Tracking**: Documents progress on ongoing projects
- **Knowledge Summaries**: Captures learning and insights over time

### Narrative Mode

Creates story-like narratives:

- **Life Story Elements**: Weaves conversations into personal narrative
- **Relationship Arcs**: Shows evolution of important relationships
- **Thematic Stories**: Creates narratives around specific themes

## Configuration

### Generation Settings

Configure generation behavior in your `config.yaml`:

```yaml
generation:
  mode: journal                # Options: journal, documentation, narrative
  style: reflective            # Options: formal, casual, reflective, analytical
  detail_level: medium         # Options: low, medium, high, comprehensive
  temperature: 0.7             # Creativity control (0.0-1.0)
  max_tokens: 2048             # Maximum tokens in generated content
  persona: 
    role: "personal knowledge curator"
    perspective: "first-person reflection"
    voice: "thoughtful and insightful"
```

### Writer Agent Settings

```yaml
agents:
  writer:
    enabled: true
    model: 
      provider: openai
      name: gpt-4o
    style:
      tone: "reflective"
      perspective: "first-person"
      vocabulary: "rich but accessible"
    content_filters:
      - "privacy_compliant"    # Ensures PII isn't included
      - "relevance_ranked"     # Prioritizes relevant content
      - "quality_threshold"    # Filters out low-value content
```

### Content Preferences

```yaml
generation:
  preferences:
    include_sentiment: true     # Include sentiment analysis results
    highlight_topics: true      # Emphasize identified topics
    chronological: true         # Maintain temporal order
    thematic_grouping: true     # Group by topics
    participant_focused: false  # Focus on specific participants
```

## Thinking Process

The generation process follows a structured thinking approach:

1. **Analysis Phase**: Understanding the context and relevant information
2. **Synthesis Phase**: Combining multiple sources of information
3. **Reflection Phase**: Adding personal insights and meaning
4. **Creation Phase**: Generating the final content

### Example Thinking Prompt

```
<thinking>
1. Analysis: I have retrieved conversations between ANON_PERSON_1 and ANON_PERSON_2 from last week focusing on their vacation planning.
2. Synthesis: Multiple conversations show they've decided on a destination, timeline, and budget. ANON_PERSON_1 shows excitement while ANON_PERSON_2 has practical concerns about logistics.
3. Reflection: This represents the planning phase of a significant joint activity, showing both excitement and responsibility.
4. Creation: I will write a reflective summary of their vacation planning process, highlighting both the excitement and practical considerations.
</thinking>
```

## Quality Controls

### Content Validation

- **Privacy Checks**: Ensures no PII is included in output
- **Relevance Filtering**: Maintains focus on meaningful content
- **Quality Thresholds**: Filters out low-value conversations

### Style Consistency

- **Tone Maintenance**: Keeps consistent voice across documents
- **Format Standards**: Maintains structural consistency
- **Terminology Consistency**: Uses consistent terms for entities and concepts

## Best Practices

- Choose the right generation mode for your needs
- Adjust detail level based on desired output length and depth
- Use appropriate style for your intended use case
- Monitor and adjust temperature for desired creativity level
- Review privacy settings to ensure appropriate anonymization