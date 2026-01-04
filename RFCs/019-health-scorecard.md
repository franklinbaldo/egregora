# RFC: Conversation Health Scorecard
**Status:** Actionable Proposal
**Date:** 2024-07-29
**Disruption Level:** Medium - Fast Path

## 1. The Vision
At the top of every generated blog post, a new "Conversation Health Scorecard" section appears. This small, visual component provides immediate, at-a-glance insights into the *dynamics* of the conversation that was just summarized. It's the first step in moving from "what was said" to "how it was said," and it ladders directly up to the [Cognitive Modeler](./018-cognitive-modeler.md) vision.

The scorecard would include simple metrics like:
- **Participation Balance:** A pie chart showing the percentage of messages contributed by each participant.
- **Sentiment Score:** An overall sentiment rating (e.g., Positive, Neutral, Mixed).
- **Inquiry Ratio:** The ratio of questions asked to statements made.

## 2. The Broken Assumption
This proposal challenges the assumption that **Egregora's output must be purely narrative.** We currently deliver a block of text, forcing the reader to intuit the underlying dynamics. This RFC proposes that we can and should present quantitative, dynamic-focused data alongside the qualitative summary.

## 3. The First Implementation Path (≤30 days)
- **Modify the Writer Agent's prompt:** Instruct the LLM to analyze the conversation dynamics and return a `conversation_health` object within its JSON output. This object should contain keys for `participation_balance` (a dictionary of author: message_count), `sentiment_score`, and `inquiry_ratio`.
- **Update the MkDocs template:** Modify the blog post template (`blog-post.html`) to check for the `conversation_health` data in the post's metadata.
- **Render the scorecard:** If the data is present, render it in a new section at the top of the post using simple HTML and CSS, or potentially a lightweight charting library.

## 4. The Value Proposition
This is the fastest way to begin delivering insights on team dynamics.
- **Immediate Value:** It provides a completely new dimension of insight to users without disrupting the existing functionality. It can immediately highlight if conversations are dominated by a few voices or if the group is engaging in healthy inquiry.
- **De-risks the Moonshot:** It proves that we can reliably extract conversational metrics from the raw chat data, which is a foundational capability for the more advanced Cognitive Modeler.
- **Builds User Habits:** It gets users accustomed to thinking about their conversations in a more data-driven way, priming them for the deeper insights the Moonshot will eventually provide.

## 5. Success Criteria
- The `egregora write` command produces posts that include the Conversation Health Scorecard.
- The scorecard accurately reflects the participation balance and other metrics from the source conversation.
- The feature is additive and does not break existing blog generation if the health data is missing.
