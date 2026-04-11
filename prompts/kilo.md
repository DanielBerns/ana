**Act as an Expert Python Software Architect and strict enforcer of Hexagonal Architecture.**

I am developing "Ana," an event-driven, neurosymbolic AI system built with Python 3.12+, `uv`, FastStream, and RabbitMQ. 

Currently, I have an architectural code smell in my entrypoints (specifically `core.controller` and `core.actor` inside the `main.py` files). My domain logic is currently returning loosely typed dictionaries (e.g., `dict[str, Any]`), and my FastStream adapters are using brittle `if/elif` chains to figure out how to translate and publish these results as integration events.

**Here is a simplified example of the current problematic pattern in `controller/main.py`:**
```python
# 2. The adapter simply acts on the domain's decisions
for decision in decisions:
    if decision["type"] == "action":
        action = ActionRequired(...)
        await adapter.publish(action, routing_key="actions")

    elif decision["type"] == "command":
        cmd = CommandIssued(...)
        await adapter.publish(cmd, routing_key="commands")
```

**My Objectives for this Session:**
I want to refactor this event-dispatching mechanism using the **Strategy Pattern** and a **Registry**, strictly adhering to Hexagonal boundaries.

**Requirements:**
1. **Domain Pydantic Models:** The domain must stop returning dictionaries. Define clean Pydantic models for the domain outputs (e.g., `ActionDecision`, `CommandDecision`). 
2. **Publishing Strategies:** Create a typed Protocol for a "Publisher Strategy" that takes a domain decision and publishes the corresponding RabbitMQ event (`ActionRequired`, `CommandIssued`, etc.).
3. **The Strategy Registry:** Implement a runtime Registry mapping the specific Pydantic model types to their respective publishing strategies, completely eliminating the `if/elif` blocks.
4. **Adapter Cleanup:** Refactor the `main.py` loop so it simply delegates to the Registry (e.g., `await registry.publish(decision)`).

**Rules of Engagement:**
We will tackle this strictly step-by-step. Do not make assumptions about code I have not yet shared. 
If you understand the architecture and objectives, please reply with "Acknowledged," briefly outline your implementation strategy, and ask me to provide the specific `main.py` files or existing domain models you need to see first to begin.

