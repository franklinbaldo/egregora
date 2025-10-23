from datetime import datetime
from .base import Agent
from ..core.models import Topic, Post


class WriterAgent(Agent):
    async def execute(
        self,
        topics: list[Topic],
        date: str,
        language: str = "pt-BR",
        max_length: int = 5000,
    ) -> Post:
        content = await self._generate_post(topics, date, language, max_length)

        media = []
        for topic in topics:
            for msg in topic.messages:
                media.extend(msg.media_files)

        post = Post(
            date=date,
            title=self._generate_title(topics),
            content=content,
            topics=topics,
            media=list(set(media)),
            metadata={
                "generated_at": datetime.now().isoformat(),
                "topic_count": len(topics),
                "language": language,
            },
        )

        return post

    async def _generate_post(
        self, topics: list[Topic], date: str, language: str, max_length: int
    ) -> str:
        topics_summary = self._format_topics_for_prompt(topics)

        prompt = f"""Generate a blog post for {date} in {language}.

Topics to cover:
{topics_summary}

Requirements:
- Write in a narrative, engaging style
- Synthesize the topics into a coherent daily summary
- Maximum {max_length} characters
- Use markdown formatting
- Include section headers for each topic
- Language: {language}

Generate the post content:"""

        system = f"You are a skilled writer creating daily summaries. Write in {language}."

        content = await self.call_llm(prompt, system)
        return content[:max_length]

    def _format_topics_for_prompt(self, topics: list[Topic]) -> str:
        lines = []
        for i, topic in enumerate(topics, 1):
            lines.append(f"\n## Topic {i}: {topic.title}")
            lines.append(f"Summary: {topic.summary}")
            lines.append(f"Keywords: {', '.join(topic.keywords)}")

            if topic.metadata.get("context"):
                lines.append("Additional Context:")
                for ctx in topic.metadata["context"]:
                    lines.append(f"  - {ctx.get('query')}: {ctx.get('result', {})}")

            lines.append("\nMessages:")
            for msg in topic.messages[:5]:
                lines.append(f"  - {msg.author}: {msg.content[:150]}")

        return "\n".join(lines)

    def _generate_title(self, topics: list[Topic]) -> str:
        if not topics:
            return "Daily Summary"

        if len(topics) == 1:
            return topics[0].title

        return f"{topics[0].title} and more"
