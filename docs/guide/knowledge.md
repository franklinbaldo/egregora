# Knowledge & RAG

Egregora uses Retrieval-Augmented Generation (RAG) to create rich, contextual knowledge from your personal data.

## Knowledge Graph Creation

Egregora transforms your conversational data into a structured knowledge graph that captures:

- **Entities**: People, places, organizations, and topics
- **Relationships**: How entities connect and interact
- **Temporal Context**: When events and conversations occurred
- **Thematic Clusters**: Topics that emerge across conversations

## Retrieval-Augmented Generation (RAG)

RAG enhances AI responses by providing relevant context from your data:

### 1. Indexing

Your anonymized conversations are indexed for efficient retrieval:

- **Message-level indexing**: Individual messages are stored with metadata
- **Conversation threading**: Related messages are grouped together
- **Entity linking**: References to the same entity are connected
- **Thematic clustering**: Messages with similar topics are grouped

### 2. Embedding

Messages are converted to vector representations that capture semantic meaning:

- **Semantic similarity**: Similar messages are closer in vector space
- **Context preservation**: Temporal and relational context is maintained
- **Privacy-safe vectors**: Based on anonymized content

### 3. Retrieval

When generating content, Egregora retrieves the most relevant information:

- **Query-aware retrieval**: Finds content relevant to the current topic
- **Temporal weighting**: Recent conversations may be weighted more heavily
- **Thematic relevance**: Prioritizes content on similar topics

## Chunking Strategy

Egregora uses intelligent chunking to balance context and efficiency:

### Conversation-Aware Chunks

Rather than arbitrarily splitting text, Egregora maintains:

- **Conversation threads**: Complete message exchanges are preserved
- **Temporal continuity**: Chunks respect natural conversation boundaries
- **Context windows**: Each chunk includes relevant preceding context

### Adaptive Chunking

The system adapts chunk size based on:

- **Message density**: More messages per chunk when content is sparse
- **Thematic consistency**: Larger chunks when topics remain stable
- **Temporal proximity**: Messages from the same time period grouped together

## Embedding Models

Egregora supports various embedding models:

### Default Embeddings

- **Model**: Sentence Transformers (multi-lingual)
- **Use case**: General purpose, multi-language support
- **Privacy**: Runs locally to avoid sending data externally

### Custom Embeddings

- **Provider support**: OpenAI, Anthropic, Ollama, etc.
- **Specialized models**: Domain-specific embedding models
- **Performance**: Potentially better quality at the cost of privacy

## Retrieval Modes

### Semantic Search

Finds content based on meaning rather than keyword matching:

```python
# Find conversations about a specific topic
retriever.search(query="discussions about our vacation planning")
```

### Temporal Search

Retrieves content from specific time periods:

```python
# Find conversations from last month about a project
retriever.search(query="project updates", date_range=last_month)
```

### Entity-Based Search

Finds content related to specific people or topics:

```python
# Find all conversations with a particular person
retriever.search(query="conversations with ANON_PERSON_1")
```

## Knowledge Graph Features

### Automatic Topic Modeling

Egregora identifies and tracks topics across conversations:

- **Topic extraction**: Identifies main themes in conversations
- **Topic evolution**: Tracks how topics change over time
- **Topic relationships**: Shows connections between related topics

### Relationship Mapping

Captures how people and entities connect:

- **Co-occurrence analysis**: Who talks to whom about what
- **Influence tracking**: Which topics influence others
- **Network visualization**: Shows relationship networks

### Context Windowing

Maintains relevant context for generation:

- **Temporal windows**: Recent activity affecting current topic
- **Thematic windows**: Related topics providing background
- **Social windows**: Ongoing conversations providing context

## Configuration

### RAG Settings

Configure RAG behavior in your `config.yaml`:

```yaml
knowledge:
  rag:
    enabled: true
    retrieval_mode: semantic      # Options: semantic, temporal, entity-based
    top_k: 5                     # Number of results to retrieve
    similarity_threshold: 0.7    # Minimum similarity for inclusion
    chunk_size: 512              # Size of text chunks in tokens
    chunk_overlap: 64            # Overlap between chunks
    
  embeddings:
    provider: local             # Options: local, openai, anthropic
    model: multi-qa-MiniLM-L6-cos-v1  # Specific embedding model
    dimensions: 384             # Vector dimensions
```

### Indexing Options

```yaml
knowledge:
  indexing:
    strategy: conversation-aware  # Maintain conversation threads
    real_time: false              # Update index during processing
    persistent: true              # Save index for reuse
    metadata_fields:              # Which metadata to index
      - timestamp
      - participants
      - topic
```

## Best Practices

- Enable RAG for richer, more contextual content generation
- Adjust `top_k` based on desired context breadth
- Use temporal search for time-sensitive queries
- Monitor similarity thresholds to balance relevance and recall
- Consider privacy implications when using external embedding providers