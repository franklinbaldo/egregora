# Egregora BDD Features

This directory contains Behavior-Driven Development (BDD) features for Egregora, written in Gherkin syntax. These features describe the behavior of the application from a user's perspective, independent of implementation details.

## Product Philosophy: "Invisible Intelligence, Visible Magic"

Egregora's magic comes from features that work automatically without configuration:
- **Contextual Memory (RAG)**: Posts reference previous discussions, creating connected narratives
- **Content Discovery (Ranking)**: Automatically identifies your best memories and conversations
- **Author Profiling**: Generates loving portraits of people from their messages

These features should:
- ✅ **Work by default** - No configuration required for 95% of users
- ✅ **Be invisible** - Users don't see "RAG" or "ranking algorithms"
- ✅ **Create magic** - Users think "Wow, how did it know?!"
- ✅ **Elevate quality** - Transform good output into great output

## Feature Hierarchy

Features are organized hierarchically by importance to the overall project:

### 01-core/ - Critical Features
The fundamental behaviors that define Egregora's core value proposition:
- **Chat-to-Blog Transformation**: Converting chat exports into blog content
- **Content Generation**: AI-powered creation of blog posts
- **Static Site Output**: Generating browsable websites

### 02-essential/ - Important Features
Essential capabilities that make Egregora magical, not just functional:
- **Input Parsing**: Reading and understanding chat export formats (WhatsApp primary)
- **Media Management**: Handling images, videos, and other media files
- **Site Initialization**: Setting up new blog projects
- **Contextual Memory (RAG)**: Making posts feel connected like a continuing story
- **Content Discovery (Ranking)**: Helping users find their best memories automatically
- **Author Profiling**: Creating emotional portraits of participants from their messages
- **Privacy Controls**: Anonymization and privacy protection

### 03-advanced/ - Value-Add Features
Advanced capabilities that enhance specific use cases:
- **Content Enrichment**: Enhancing posts with URL previews and media descriptions

### 04-specialized/ - Specialized Features
Features that address specific use cases and requirements:
- **Command System**: In-chat commands for user control (experimental)
- **Configuration Management**: Customizing behavior and output (for power users)
- **Resume & Checkpoint**: Continuing interrupted processing

### 05-utility/ - Supporting Features
Utility features that support development and troubleshooting:
- **Diagnostics**: Health checks and validation
- **Demo Generation**: Sample content for evaluation

## Feature File Naming Convention

Feature files follow the pattern: `NN-feature-name.feature`
- `NN`: Two-digit sequence number indicating relative importance within the directory
- `feature-name`: Kebab-case descriptive name
- `.feature`: Gherkin feature file extension

## Gherkin Syntax

Each feature file uses standard Gherkin syntax:
- **Feature**: High-level description of functionality
- **Background**: Common setup steps for all scenarios
- **Scenario**: Specific behavior example
- **Scenario Outline**: Parameterized scenario with examples
- **Given**: Initial context and preconditions
- **When**: Actions performed
- **Then**: Expected outcomes
- **And**: Additional steps of the same type

## Implementation-Agnostic

These features intentionally avoid referencing:
- Specific technologies (DuckDB, LanceDB, Pydantic-AI, etc.)
- Implementation details (classes, functions, modules)
- Internal architecture decisions

Instead, they focus on:
- User-observable behaviors
- Inputs and outputs
- Business value and outcomes
- User workflows and interactions

## Running Features

While these features are currently documentation, they can be used with BDD testing frameworks like:
- `behave` (Python)
- `pytest-bdd` (Python)
- `cucumber` (Ruby/JavaScript)

## Contributing

When adding new features:
1. Place them in the appropriate hierarchy level
2. Use clear, behavior-focused language
3. Avoid implementation details
4. Write from the user's perspective
5. Include relevant examples and edge cases

---

*These features describe the behavior of Egregora as of January 2026.*
