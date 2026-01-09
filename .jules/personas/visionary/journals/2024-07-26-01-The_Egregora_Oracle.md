## 🔮 2024-07-26 - Moonshot + Quick Win: The Egregora Oracle & Related Concepts API
**The Napkin Sketch (Rejected Ideas):**
- **Egregora Zeitgeist:** An agent that predicts emerging themes and disagreements. Powerful, but the value is less direct than answering a specific user question. It's a "push" model, while the Oracle is a "pull" model, which is a better starting point.
- **Radio Free Egregora:** An audio summary of the chat. This is a change in *modality*, not a change in *interactivity*. It's still a passive, retrospective artifact.
- **Egregora as a Chatbot:** Too generic. "Chatbot" is an implementation detail. "The Oracle" is a product vision that defines *what* the bot does: it provides access to the group's single source of truth.

**Selected Moonshot:** [The Egregora Oracle](../../../../RFCs/001-the-egregora-oracle.md)
**Selected Quick Win:** [Related Concepts API](../../../../RFCs/002-related-concepts-api.md)

**Why this pairing works:** The Oracle is the grand vision of a living, interactive knowledge base. It's a huge leap from the current static, batch-processed blog. The Related Concepts API is the perfect "trojan horse" to begin this journey. It's a small, non-disruptive change that delivers immediate value to the existing product (better related posts) while simultaneously building the foundational query engine the Oracle will depend on. It de-risks the entire moonshot by proving the core technical hypothesis—that we can effectively query our knowledge base for relevant concepts—within the safety of the current architecture.
