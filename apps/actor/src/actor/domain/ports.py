from typing import Protocol, List, Dict

class LlmProvider(Protocol):
    """Port for Language Model generation."""
    async def generate_reply(self, chat_history: List[Dict[str, str]], system_prompt: str) -> str:
        """Takes a list of message dicts (role/content) and returns the generated text."""
        ...
