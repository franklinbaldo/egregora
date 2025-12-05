class TestModel:
    def __init__(self, call_tools=None):
        self.call_tools = call_tools or []

    def gen_tool_args(self, tool_def):
        return {}
