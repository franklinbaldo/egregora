from collections import Counter
from .base import Agent
from ..core.models import Message, Profile


class ProfilerAgent(Agent):
    async def execute(
        self,
        messages: list[Message],
        min_messages: int = 10,
    ) -> list[Profile]:
        author_messages = {}
        for msg in messages:
            if msg.author not in author_messages:
                author_messages[msg.author] = []
            author_messages[msg.author].append(msg)

        profiles = []
        for author, msgs in author_messages.items():
            if len(msgs) < min_messages:
                continue

            profile = await self._create_profile(author, msgs)
            profiles.append(profile)

        return profiles

    async def _create_profile(self, author: str, messages: list[Message]) -> Profile:
        prompt = self._build_profile_prompt(author, messages)
        summary = await self.call_llm(prompt)

        topics = self._extract_topics(messages)
        activity = self._analyze_activity(messages)

        slug = author.lower().replace(" ", "-")

        return Profile(
            author=author,
            slug=slug,
            message_count=len(messages),
            topics=topics,
            summary=summary,
            activity=activity,
        )

    def _build_profile_prompt(self, author: str, messages: list[Message]) -> str:
        recent = messages[:10]
        sample = "\n".join([f"- {m.content[:200]}" for m in recent])

        return f"""Analyze this participant's activity and create a brief profile.

Author: {author}
Total messages: {len(messages)}

Recent messages:
{sample}

Write a 2-3 sentence summary of their participation style and main interests."""

    def _extract_topics(self, messages: list[Message]) -> list[str]:
        all_keywords = []
        for msg in messages:
            if "keywords" in msg.metadata:
                all_keywords.extend(msg.metadata["keywords"])

        if all_keywords:
            counter = Counter(all_keywords)
            return [word for word, _ in counter.most_common(5)]

        return []

    def _analyze_activity(self, messages: list[Message]) -> dict:
        return {
            "total_messages": len(messages),
            "avg_message_length": sum(len(m.content) for m in messages) / len(messages),
            "has_media": any(m.media_files for m in messages),
        }
