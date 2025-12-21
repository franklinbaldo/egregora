# Example Skill: Conversation Statistics

This skill enables agents to generate detailed statistics about conversation patterns, message frequency, and author participation.

## Capabilities

- Calculate message counts per author
- Analyze temporal patterns (hourly, daily, weekly)
- Identify conversation threads and topics
- Generate summary statistics with key insights

## When to Use This Skill

Use this skill when you need to:
- Answer questions about conversation patterns ("Who posts the most?")
- Generate engagement metrics
- Identify peak activity times
- Compare author participation levels

## Instructions for Sub-Agents

When you're loaded with this skill, follow these steps:

### 1. Understand the Task

Parse the task description to identify:
- What statistics are needed (counts, distributions, trends)
- Time range to analyze (if specified)
- Specific authors to focus on (if any)

### 2. Query the Data

Use your access to the conversation data to:
- Filter messages by time range
- Group by author, hour, day, etc.
- Count messages per group
- Calculate percentages and distributions

### 3. Generate Insights

Look for:
- **Participation patterns**: Who are the most active authors?
- **Temporal patterns**: When is the conversation most active?
- **Engagement trends**: Are messages increasing or decreasing over time?
- **Thread structure**: Are there concentrated discussion periods?

### 4. Format Summary

Structure your findings as:

```
[Task Description Summary]

Key Findings:
1. [Most important insight]
2. [Second important insight]
3. [Third important insight]

Detailed Statistics:
- Metric 1: value (percentage)
- Metric 2: value (percentage)
- ...

Observations:
[1-2 paragraphs explaining patterns and notable trends]
```

### 5. Call end_skill_use()

When your analysis is complete, call:

```python
end_skill_use(summary)
```

Where `summary` contains all the findings formatted as above.

## Example Tasks and Expected Outputs

### Example 1: Message Count by Author

**Task**: "Generate statistics showing message counts per author"

**Expected Summary**:
```
Message Count by Author

Key Findings:
1. Alice is the most active with 342 messages (28% of total)
2. Bob and Charlie have similar activity (210 and 198 messages)
3. 15 total authors, but top 5 account for 75% of messages

Detailed Statistics:
- Alice: 342 messages (28%)
- Bob: 210 messages (17%)
- Charlie: 198 messages (16%)
- Dave: 156 messages (13%)
- Eve: 134 messages (11%)
- Others: 182 messages (15%)
- Total: 1,222 messages

Observations:
The conversation shows a typical power law distribution with a small number
of highly engaged participants driving most of the activity. The top 5 authors
account for 75% of all messages, suggesting a core group of active participants.
```

### Example 2: Hourly Distribution

**Task**: "Analyze message distribution by hour of day"

**Expected Summary**:
```
Hourly Message Distribution

Key Findings:
1. Peak activity between 2pm-4pm (320 messages, 26%)
2. Minimal activity 12am-6am (45 messages, 4%)
3. Secondary peak around 8pm-10pm (180 messages, 15%)

Detailed Statistics:
- 12am-6am: 45 messages (4%)
- 6am-12pm: 280 messages (23%)
- 12pm-6pm: 615 messages (50%)
- 6pm-12am: 282 messages (23%)

Observations:
The conversation follows a typical work-hours pattern with peak engagement
during mid-afternoon. This suggests participants are likely in similar time
zones and using the chat during breaks or after core work hours. The evening
peak indicates continued engagement after traditional work hours.
```

## Tips for Success

1. **Be specific**: Don't just say "many messages" - give exact counts and percentages
2. **Compare and contrast**: Highlight differences between groups/periods
3. **Explain patterns**: Don't just report numbers - interpret what they mean
4. **Use context**: Reference the time range being analyzed
5. **Stay concise**: Summary should be 2-4 paragraphs max (unless task asks for more detail)

## Common Pitfalls to Avoid

❌ **Don't** return raw data dumps (CSV-style lists)
❌ **Don't** skip the `end_skill_use()` call
❌ **Don't** include debugging information in the summary
❌ **Don't** make assumptions about data without verifying
✅ **Do** structure findings clearly with headings and bullets
✅ **Do** provide percentages alongside raw counts
✅ **Do** highlight the most interesting patterns
✅ **Do** keep the summary actionable and insightful

## Testing This Skill

To test this skill, try these sample tasks:

1. "Generate statistics showing message counts per author"
2. "Analyze message distribution by hour of day"
3. "Show weekly message trends over the last month"
4. "Compare activity levels between weekdays and weekends"

Each should produce a clear, well-structured summary with key findings and detailed statistics.
