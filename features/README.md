# Egregora BDD Features

This directory contains Behavior-Driven Development (BDD) features for Egregora, written in Gherkin syntax. These features describe the behavior of the application from a user's perspective, independent of implementation details.

## Feature Hierarchy

Features are organized hierarchically by importance to the overall project:

### 01-core/ - Critical Features
The fundamental behaviors that define Egregora's core value proposition:
- **Chat-to-Blog Transformation**: Converting chat exports into blog content
- **Content Generation**: AI-powered creation of blog posts
- **Static Site Output**: Generating browsable websites

### 02-essential/ - Important Features
Essential capabilities for the application to function effectively:
- **Input Parsing**: Reading and understanding various chat export formats
- **Media Management**: Handling images, videos, and other media files
- **Site Initialization**: Setting up new blog projects

### 03-advanced/ - Value-Add Features
Advanced capabilities that enhance the quality and value of generated content:
- **Content Evaluation**: Ranking and comparing generated posts
- **Content Enrichment**: Enhancing posts with URL previews and media descriptions
- **Author Profiling**: Generating insights about chat participants
- **Contextual Memory**: Using conversation history to improve content generation

### 04-specialized/ - Specialized Features
Features that address specific use cases and requirements:
- **Privacy Controls**: Anonymization and opt-out capabilities
- **Command System**: In-chat commands for user control
- **Configuration Management**: Customizing behavior and output
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
