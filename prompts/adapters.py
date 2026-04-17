class Registry:
    def __init__(self) -> None:
        self._table: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}

    @property
    def table(self) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
        return self._table

    def add(self, key: str, action: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self.table[key] = action
