from .registry import Tool
from ..privacy import validate_newsletter_privacy


class PrivacyTool(Tool):
    async def execute(self, content: str) -> dict:
        try:
            validate_newsletter_privacy(content)
            return {"valid": True, "violations": []}
        except Exception as e:
            return {"valid": False, "violations": [str(e)]}
