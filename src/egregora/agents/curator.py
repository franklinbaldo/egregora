import json
from .base import Agent
from ..core.models import Message, Topic


class CuratorAgent(Agent):
    async def execute(
        self,
        messages: list[Message],
        min_length: int = 15,
        max_topics: int = 10,
    ) -> list[Topic]:
        filtered = [m for m in messages if len(m.content) >= min_length]

        if not filtered:
            return []

        prompt = self._build_clustering_prompt(filtered, max_topics)
        system = "You are a content curator. Analyze messages and cluster them into coherent topics. Return only valid JSON."

        response = await self.call_llm(prompt, system)
        topics = self._parse_topics(response, filtered)

        return topics[:max_topics]

    def _build_clustering_prompt(self, messages: list[Message], max_topics: int) -> str:
        msg_texts = "\n".join(
            [f"[{i}] {m.author}: {m.content[:200]}" for i, m in enumerate(messages)]
        )

        return f"""Analyze these {len(messages)} messages and cluster them into up to {max_topics} coherent topics.

Messages:
{msg_texts}

Return a JSON array of topics with this structure:
[
  {{
    "title": "Topic title",
    "message_indices": [0, 1, 5],
    "summary": "Brief summary",
    "keywords": ["keyword1", "keyword2"],
    "relevance_score": 0.8
  }}
]

Focus on quality over quantity. Only group messages that genuinely belong together."""

    def _parse_topics(self, response: str, messages: list[Message]) -> list[Topic]:
        try:
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            data = json.loads(response)
            topics = []

            for i, item in enumerate(data):
                msg_indices = item.get("message_indices", [])
                topic_messages = [messages[idx] for idx in msg_indices if idx < len(messages)]

                topic = Topic(
                    id=f"topic_{i}",
                    title=item.get("title", "Untitled"),
                    messages=topic_messages,
                    summary=item.get("summary"),
                    relevance_score=item.get("relevance_score", 0.5),
                    keywords=item.get("keywords", []),
                )
                topics.append(topic)

            return topics
        except Exception:
            return []
