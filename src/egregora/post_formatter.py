from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import PipelineConfig
    from .enrichment import EnrichmentResult
    from .models import GroupSource


class PostFormatter:
    """Cleans and formats a generated post for blog-ready output."""

    def __init__(self, config: PipelineConfig):
        self.config = config

    def format(
        self,
        text: str,
        *,
        source: GroupSource,
        enrichment_result: EnrichmentResult | None = None,
    ) -> str:
        """Applies all formatting and cleaning rules to the post content."""

        # 1. Clean double frontmatter
        text = self._clean_frontmatter(text)

        # 2. Improve readability (e.g., paragraph breaks)
        text = self._improve_readability(text)

        # 3. Format links
        text = self._format_links(text, enrichment_result)

        # 4. Format media (This is already partially handled, but we can refine it here)
        text = self._format_media(text)

        return text.strip()

    def _clean_frontmatter(self, text: str) -> str:
        """Removes spurious YAML frontmatter blocks from the body."""

        # Find all frontmatter blocks
        blocks = re.findall(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL | re.MULTILINE)

        # If there's more than one, we assume the LLM added a spurious one.
        # We keep the last one, as our own frontmatter is added at the end.
        if len(blocks) > 1:
            # Remove all but the last occurence
            parts = text.split("---")
            # The structure is [before, fm1, content, fm2, after]
            # We want to reconstruct it as [before, content, fm2, after]
            # This is a bit naive, a better approach would be to find the indices
            # and remove the first block.
            # For now, let's just remove all "---" and the content of the first block
            text = text.replace(f"---{blocks[0]}---", "", 1)

        # A simpler approach: just remove any "---" from the body,
        # as we will add our own valid one later.
        cleaned_text = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text.strip(), flags=re.DOTALL | re.MULTILINE)
        return cleaned_text

    def _improve_readability(self, text: str) -> str:
        """Ensures proper paragraph breaks and other readability improvements."""

        # Replace single newlines with double newlines to create paragraphs,
        # but be careful not to mess up markdown lists or code blocks.
        # This is a complex task, so we'll start simple.

        # Ensure at least one blank line between paragraphs
        text = re.sub(r"([^\n])\n([^\n])", r"\1\n\n\2", text)
        return text

    def _format_links(self, text: str, enrichment_result: EnrichmentResult | None) -> str:
        """Converts raw URLs to markdown links, using enrichment data if available."""

        if not enrichment_result:
            return text

        url_pattern = re.compile(r"https?://[^\s/$.?#].[^\s]*")

        def replace_link(match):
            url = match.group(0)
            # Find enrichment data for this URL
            for item in enrichment_result.items:
                if item.reference.url == url and item.analysis:
                    title = item.analysis.title or item.analysis.summary or url
                    title = title.replace('"', "'") # Avoid issues with markdown
                    return f'[{title}]({url})'
            return url # Return original URL if no enrichment found

        return url_pattern.sub(replace_link, text)

    def _format_media(self, text: str) -> str:
        """Ensures media references are correctly formatted."""
        # This is mostly handled by MediaExtractor, but we can add refinements here
        # For example, ensuring ![alt](path) syntax is used.
        # This is a placeholder for now.
        return text