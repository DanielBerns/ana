Note that I am trying to explore implementations, and to clarify ideas. My answers may be weird, or not usual. I want your non flattering answers and questions.

1. The targets are:
  1.1. core.controller: main.py
  1.2. core.actor: main.py

2. Some functions are coded with the pattern if ... then ... elif ... ;  I want to include more options in these functions.
3. I want to respond to new events.
4. The inputs are events and the outputs of these strategies are dict[str, Any]
5. I would like to use incoming events via RabbitMQ to select and inject new strategies

1. Yes, I like a Registry. 
2. Use Pydantic models.
3. For example, in controller.main, the code is this 

        # 2. The adapter simply acts on the domain's decisions
        for decision in decisions:
            if decision["type"] == "action":
                action = ActionRequired(
                    correlation_id=event.correlation_id,
                    action_type=decision["action_type"],
                    payload=decision["payload"]
                )
                await adapter.publish(action, routing_key="actions")
                logger.info("action_issued", action=decision["action_type"])

            elif decision["type"] == "command":
                cmd = CommandIssued(
                    correlation_id=event.correlation_id,
                    instruction=decision["instruction"],
                    context_data=decision.get("context_data", {})
                )
                await adapter.publish(cmd, routing_key="commands")
                logger.info("command_issued", command=decision["instruction"])

