from typing import Protocol, Any
import yaml
import csv
import io

class Loader(Protocol):
    def serialize(self, data: list[dict[str, Any]], **kwargs) -> str: ...

class YamlLoader:
    """Serializes the transformed data into a highly readable YAML document."""
    def serialize(self, data: list[dict[str, Any]], **kwargs) -> str:
        # default_flow_style=False ensures standard block-style YAML formatting
        return yaml.dump(data, allow_unicode=True, default_flow_style=False)

class CsvLoader:
    """Flattens the dictionaries into a tabular CSV format."""
    def serialize(self, data: list[dict[str, Any]], **kwargs) -> str:
        if not data:
            return ""

        output = io.StringIO()
        # Derive headers from the keys of the first dictionary
        keys = data[0].keys()
        dict_writer = csv.DictWriter(output, fieldnames=keys)

        dict_writer.writeheader()
        dict_writer.writerows(data)
        return output.getvalue()
