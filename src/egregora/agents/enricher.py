import json
from .base import Agent
from ..core.models import Topic


class EnricherAgent(Agent):
    async def execute(
        self,
        topics: list[Topic],
        max_enrichments: int = 5,
    ) -> list[Topic]:
        enriched = []

        for topic in topics:
            plan = await self._create_enrichment_plan(topic, max_enrichments)
            context = await self._gather_context(plan)

            topic.metadata["enrichment_plan"] = plan
            topic.metadata["context"] = context

            enriched.append(topic)

        return enriched

    async def _create_enrichment_plan(self, topic: Topic, max_enrichments: int) -> dict:
        prompt = f"""Create an enrichment plan for this topic:

Title: {topic.title}
Summary: {topic.summary}
Keywords: {', '.join(topic.keywords)}

Available tools: {list(self.tools._tools.keys())}

Return a JSON object with queries to run:
{{
  "queries": [
    {{"tool": "rag", "query": "search query"}},
    {{"tool": "web", "query": "web search"}}
  ]
}}

Maximum {max_enrichments} queries."""

        response = await self.call_llm(prompt)

        try:
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            plan = json.loads(response)
            return plan
        except Exception:
            return {"queries": []}

    async def _gather_context(self, plan: dict) -> list[dict]:
        context = []

        for query_spec in plan.get("queries", []):
            tool_name = query_spec.get("tool")
            query = query_spec.get("query")

            if not tool_name or not query:
                continue

            try:
                result = await self.tools.execute(tool_name, query=query)
                context.append({"tool": tool_name, "query": query, "result": result})
            except Exception:
                continue

        return context
