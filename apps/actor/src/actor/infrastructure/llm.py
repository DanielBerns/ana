import asyncio
from typing import List, Dict

class DummyLlmAdapter:
    """A simulated LLM for testing the event pipeline."""

    async def generate_reply(self, chat_history: List[Dict[str, str]], system_prompt: str) -> str:
        # Simulate network delay for API inference
        await asyncio.sleep(1.5)

        # Echo back the last user message to prove it received the context
        last_message = "Nothing"
        if chat_history and chat_history[-1]["role"] == "user":
            last_message = chat_history[-1]["content"]

        return f"Hello! I am Ana's Dummy LLM. You just said: '{last_message}'. I see {len(chat_history)} messages in our history."
