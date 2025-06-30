from agent import Agent


class Runner:
    """Minimal async runner shim used only in tests."""

    @staticmethod
    async def run(agent, input=None, **kwargs):
        class _Res:
            def __init__(self, items):
                self.new_items = items or []
                self.final_output = items or []

        return _Res(input)



class ItemHelpers:
    """Helper to pull text from message items."""

    @staticmethod
    def text_message_outputs(items):
        if isinstance(items, list):
            return "\n".join(str(i.get("content", i)) for i in items)
        return str(items)

