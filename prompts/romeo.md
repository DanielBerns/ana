Consider the uploaded file inbound_node.py. I want to refactor the lines 

        # 1. Simulate fetching data from an external source based on command parameters
        if command.parameters.get("simulate_fatal_error"):
            # Simulate a database crash or out-of-memory error
            raise RuntimeError("Unexpected fatal system state!")

        if command.parameters.get("simulate_api_down"):
            # Simulate an expected, handled domain failure
            raise ExpectedDomainException("External API returned 503 Unavailable.")

        # Simulate a successful fetch payload
        raw_payload = b'{"status": "success", "data": "Sample external data"}'
        mime_type = "application/json"

        # 2. Save to the Resource Repository
        metadata = {"source_node": command.target_node_id, "command_id": command.header.message_id}
        resource_uri = await repository.save(raw_payload, metadata)

I want to replace these lines with some dependecy injection, to be able to run several tasks in parallel (getting and posting resources in websites).
Please, make a draft proposal for this feature.

I want to use a Registry like this

    class Registry:
        def __init__(self) -> None:
            self._table: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
    
        @property
        def table(self) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
            return self._table
    
        def add(self, key: str, gateway: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
            self.table[key] = gateway
            

Then, in the handle_inbound_command 

       action_key = command.parameters.get("action_key", "")
       action_parameters = command.parameters.get("action_parameters", {})
       action = registry.table.get(action_key, default_action)
       result = action(action_parameters)
       
I am exploring how to design and implement this code. Please, give me your thoughts about it. Be honest about it.
       
