from typing import Protocol, Any
from bs4 import BeautifulSoup
import re

class Transformer(Protocol):
    def transform(self, raw_data: dict[str, Any], **kwargs) -> list[dict[str, Any]]: ...

class DOMTransformer:
    """Uses BeautifulSoup to target specific CSS selectors in an HTML document."""
    def transform(self, raw_data: dict[str, Any], **kwargs) -> list[dict[str, Any]]:
        target_selector = kwargs.get("target_selector", "p")
        content = raw_data.get("content", "")
        soup = BeautifulSoup(content, "html.parser")

        elements = soup.select(target_selector)
        return [{"text": el.get_text(strip=True)} for el in elements if el.get_text(strip=True)]

class RegexTransformer:
    """Applies regular expressions to extract structured patterns from flat text."""
    def transform(self, raw_data: dict[str, Any], **kwargs) -> list[dict[str, Any]]:
        pattern = kwargs.get("pattern", r"(.*)")
        content = raw_data.get("content", "")
        matches = re.finditer(pattern, content, re.MULTILINE)
        return [{"match": match.group(0), "groups": match.groups()} for match in matches]

class JSONPathTransformer:
    """Extracts target fields from nested API responses."""
    def transform(self, raw_data: dict[str, Any], **kwargs) -> list[dict[str, Any]]:
        # For simplicity, we assume we are extracting a specific root key containing a list
        target_key = kwargs.get("target_key")
        if target_key and target_key in raw_data:
            return raw_data[target_key]
        return [raw_data] # Return as list for uniform loader processing
