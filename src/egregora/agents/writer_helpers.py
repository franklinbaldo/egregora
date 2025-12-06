def _process_tool_result(content: Any) -> dict[str, Any] | None:
    """Parse tool result content into a dictionary if valid."""
    if isinstance(content, str):
        try:
            return json.loads(content)
        except (ValueError, json.JSONDecodeError):
            return None
    if hasattr(content, "model_dump"):
        return content.model_dump()
    if isinstance(content, dict):
        return content
    return None
