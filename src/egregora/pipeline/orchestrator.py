import logging
from pathlib import Path
from datetime import datetime
from ..core.models import Message, Post, Profile
from ..core.config import PipelineConfig
from ..agents import CuratorAgent, EnricherAgent, WriterAgent, ProfilerAgent
from ..tools.registry import ToolRegistry
from ..tools.rag_tool import RAGTool
from ..tools.privacy_tool import PrivacyTool
from ..privacy import validate_newsletter_privacy


logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.tools = self._setup_tools()
        self.curator = CuratorAgent(
            model=config.llm.model,
            api_key=config.llm.api_key,
            tools=self.tools,
        )
        self.enricher = EnricherAgent(
            model=config.llm.model,
            api_key=config.llm.api_key,
            tools=self.tools,
        )
        self.writer = WriterAgent(
            model=config.llm.model,
            api_key=config.llm.api_key,
            tools=self.tools,
        )
        self.profiler = ProfilerAgent(
            model=config.llm.model,
            api_key=config.llm.api_key,
            tools=self.tools,
        )

    def _setup_tools(self) -> ToolRegistry:
        registry = ToolRegistry()

        if self.config.enricher.enable_rag:
            rag_dir = self.config.output_dir / "rag"
            rag_dir.mkdir(parents=True, exist_ok=True)
            registry.register("rag", RAGTool(persist_dir=rag_dir))

        registry.register("privacy", PrivacyTool())

        return registry

    async def run(self, messages: list[Message], date: str) -> Post:
        logger.info(f"Processing {len(messages)} messages for {date}")

        if self.config.curator.enabled:
            logger.info("Curating topics...")
            topics = await self.curator.execute(
                messages=messages,
                min_length=self.config.curator.min_message_length,
                max_topics=self.config.curator.max_topics_per_day,
            )
            logger.info(f"Found {len(topics)} topics")
        else:
            topics = []

        if self.config.enricher.enabled and topics:
            logger.info("Enriching topics...")
            topics = await self.enricher.execute(
                topics=topics,
                max_enrichments=self.config.enricher.max_enrichments_per_post,
            )

        if self.config.writer.enabled:
            logger.info("Generating post...")
            post = await self.writer.execute(
                topics=topics,
                date=date,
                language=self.config.writer.language,
                max_length=self.config.writer.max_post_length,
            )
        else:
            post = Post(date=date, title="", content="", topics=topics)

        logger.info("Validating privacy...")
        try:
            validate_newsletter_privacy(post.content)
        except Exception as e:
            logger.warning(f"Privacy validation failed: {e}")
            raise

        return post

    async def generate_profiles(self, messages: list[Message]) -> list[Profile]:
        if not self.config.profiler.enabled:
            return []

        logger.info("Generating profiles...")
        profiles = await self.profiler.execute(
            messages=messages,
            min_messages=self.config.profiler.min_messages,
        )
        logger.info(f"Generated {len(profiles)} profiles")
        return profiles

    def save_post(self, post: Post):
        output_dir = self.config.output_dir / "posts"
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{post.date}.md"
        filepath = output_dir / filename

        content = self._format_post_markdown(post)
        filepath.write_text(content, encoding="utf-8")

        logger.info(f"Saved post to {filepath}")

    def _format_post_markdown(self, post: Post) -> str:
        lines = [
            "---",
            f"title: {post.title}",
            f"date: {post.date}",
            "---",
            "",
            post.content,
        ]
        return "\n".join(lines)
