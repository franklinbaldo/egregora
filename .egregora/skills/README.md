# Egregora Skills

Skills are reusable capability extensions that agents can load on-demand using the `use_skill` tool.

## How Skills Work

1. **Agent calls `use_skill(skill_name, task)`**: The parent agent identifies a task that requires specialized knowledge or capabilities.

2. **Sub-agent spawning**: Egregora creates a sub-agent with:
   - Same model and tools as the parent
   - Parent's full context (conversations, profiles, etc.)
   - **Plus** the skill content injected into system prompt
   - Access to special `end_skill_use()` tool

3. **Isolated execution**: The sub-agent works independently:
   - Uses skill instructions to complete the task
   - Can call any parent tools
   - Signals completion with `end_skill_use(summary)`

4. **Summary return**: Parent agent receives only the summary, keeping context clean.

## Creating a Skill

Skills are plain text files (Markdown recommended) in `.egregora/skills/`:

**File naming**: `skill-name.md` (use `.md`, `.txt`, or `.skill` extension)

**Content structure**:
```markdown
# Skill Name

Brief description of what this skill enables.

## Capabilities

- Capability 1
- Capability 2

## Instructions

Step-by-step guide for the agent:
1. First, do X
2. Then, analyze Y
3. Finally, call end_skill_use(summary)

## Examples

Example task: "Analyze XYZ"
Expected output: "Found 3 key insights..."

## Tips

- Tip 1
- Tip 2
```

## Using Skills

### From an Agent

When an Egregora agent needs specialized capabilities:

```python
# Agent calls the use_skill tool
result = await use_skill(
    skill_name="github-api",
    task="Analyze PR #123 for security vulnerabilities"
)
# result contains the sub-agent's summary
```

### Completion Signal

Sub-agents should call `end_skill_use()` when done:

```python
# Inside sub-agent execution
summary = """
Analyzed PR #123. Found 2 security issues:
1. SQL injection in auth/login.py (P0 severity)
2. XSS vulnerability in web/comments.js (P1 severity)

Recommended fixes: ...
"""

end_skill_use(summary)
```

If the sub-agent finishes naturally without calling `end_skill_use()`, Egregora uses the final response as the summary.

## Available Skills

Skills in this directory:

- **example-skill.md**: Example skill template demonstrating structure
- *(add your custom skills here)*

## Example Workflows

### GitHub PR Analysis

**Parent agent**: "I need to analyze PR #123 for security issues"

**Tool call**: `use_skill("github-api", "Analyze PR #123 for security vulnerabilities")`

**Sub-agent**:
1. Loads GitHub skill instructions
2. Fetches PR content using GitHub API
3. Analyzes code changes for security patterns
4. Calls `end_skill_use("Found 2 vulnerabilities: ...")`

**Parent receives**: Only the summary (not the full API calls/analysis process)

### Data Analysis

**Parent agent**: "I need statistics about conversation patterns"

**Tool call**: `use_skill("data-analysis", "Generate hourly message distribution stats")`

**Sub-agent**:
1. Loads data analysis instructions
2. Queries conversation database
3. Generates charts and statistics
4. Calls `end_skill_use("Message distribution: peak at 2pm-4pm...")`

**Parent receives**: Summary with key findings

## Benefits

✅ **Context isolation**: Skill work doesn't bloat parent context
✅ **Reusability**: Same skill for multiple agents/tasks
✅ **Specialization**: Deep domain knowledge without permanent overhead
✅ **Composability**: Combine skills for complex workflows

## Best Practices

1. **Keep skills focused**: One skill = one domain (e.g., "github-api" not "general-coding")
2. **Write clear instructions**: Sub-agents need step-by-step guidance
3. **Include examples**: Show expected inputs/outputs
4. **Test independently**: Create test tasks to validate skill behavior
5. **Document completion criteria**: When should sub-agent call `end_skill_use()`?

## Troubleshooting

**Skill not found error**:
- Check file exists in `.egregora/skills/`
- Verify file extension is `.md`, `.txt`, or `.skill`
- Check file is not empty

**Sub-agent doesn't use skill**:
- Ensure skill instructions are clear and actionable
- Add examples showing how to use the capability
- Check skill content isn't too long (model context limits)

**Parent doesn't receive summary**:
- Verify sub-agent calls `end_skill_use(summary)`
- Check summary is not empty string
- Review logs for sub-agent errors
