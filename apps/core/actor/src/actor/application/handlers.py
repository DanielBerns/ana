from typing import Protocol, Dict

import httpx

from shared.events import CommandIssued, TaskCompleted
from actor.domain.classifier import IntentClassifier
from actor.domain.extractor import FactExtractor

class CommandHandlerStrategy(Protocol):
    """Port defining how an instruction is executed."""
    async def execute(self, command: CommandIssued) -> TaskCompleted:
        ...

class EvaluateIntentHandler:
    def __init__(self, classifier: IntentClassifier):
        self.classifier = classifier

    async def execute(self, command: CommandIssued) -> TaskCompleted:
        raw_text = command.context_data.get("raw_text", "")

        # Domain logic delegation
        result = self.classifier.classify(raw_text)

        return TaskCompleted(
            correlation_id=command.correlation_id,
            task_name=command.instruction,
            status="success",
            result_summary={"intent": result["intent"], "confidence": result["confidence"]}
        )

class ExtractFactsHandler:
    def __init__(self, extractor: FactExtractor, store_url: str):
        self.extractor = extractor
        self.store_url = store_url

    async def execute(self, command: CommandIssued) -> TaskCompleted:
        uri = command.context_data.get("uri")

        # 1. Fetch physical data (Infrastructure orchestration)
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.store_url}/blobs/{uri}")
            html_content = resp.json().get("content", "")

        # 2. Extract symbolic facts (Domain logic delegation)
        clean_text = self.extractor.clean_html(html_content)
        keywords = self.extractor.extract_keywords(clean_text)

        return TaskCompleted(
            correlation_id=command.correlation_id,
            task_name=command.instruction,
            status="success",
            result_summary={"keywords": keywords, "uri": uri}
        )

class CommandHandlerRegistry:
    def __init__(self):
        # Maps the instruction string to its corresponding Application Strategy
        self._handlers: Dict[str, CommandHandlerStrategy] = {}

    def register(self, instruction: str, handler: CommandHandlerStrategy) -> None:
        self._handlers[instruction] = handler

    async def handle(self, command: CommandIssued) -> TaskCompleted:
        handler = self._handlers.get(command.instruction)
        if not handler:
            raise ValueError(f"No handler registered for instruction: '{command.instruction}'")

        return await handler.execute(command)
