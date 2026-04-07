from typing import Protocol, Any
import yaml
import csv
import io

class Loader(Protocol):
    def serialize(self, data: list[dict[str, Any]], parameters: dict[str, str] | None = None) -> str: ...

class YamlLoader:
    """Serializes the transformed data into a highly readable YAML document."""
    def serialize(self, data: list[dict[str, Any]], parameters: dict[str, str] | None = None) -> str:
        params = parameters or {}
        return yaml.dump(data, allow_unicode=True, default_flow_style=False)

class CsvLoader:
    """Flattens the dictionaries into a tabular CSV format."""
    def serialize(self, data: list[dict[str, Any]], parameters: dict[str, str] | None = None) -> str:
        params = parameters or {}
        if not data:
            return ""

        output = io.StringIO()
        keys = data[0].keys()
        dict_writer = csv.DictWriter(output, fieldnames=keys)

        dict_writer.writeheader()
        dict_writer.writerows(data)
        return output.getvalue()
