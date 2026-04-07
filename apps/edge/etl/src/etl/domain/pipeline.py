from typing import Any
from .extractors import HttpExtractor, SeleniumExtractor, FileSystemExtractor, ApiExtractor
from .transformers import DOMTransformer, RegexTransformer, JSONPathTransformer
from .loaders import YamlLoader, CsvLoader

class ETLPipeline:
    """Dynamically constructs and executes a data pipeline based on configuration."""

    def __init__(self):
        self.extractors = {
            "HttpExtractor": HttpExtractor(),
            "SeleniumExtractor": SeleniumExtractor(),
            "FileSystemExtractor": FileSystemExtractor(),
            "ApiExtractor": ApiExtractor()
        }
        self.transformers = {
            "DOMTransformer": DOMTransformer(),
            "RegexTransformer": RegexTransformer(),
            "JSONPathTransformer": JSONPathTransformer()
        }
        self.loaders = {
            "YamlLoader": YamlLoader(),
            "CsvLoader": CsvLoader()
        }

    async def execute(self, config: dict[str, Any]) -> str:
        """
        Executes the E -> T -> L sequence.
        Expected config format:
        {
            "source": "https://...",
            "extractor": "HttpExtractor",
            "transformer": "DOMTransformer",
            "loader": "YamlLoader",
            "extractor_parameters": {"verify": "false"},
            "transformer_parameters": {"target_selector": "article"},
            "loader_parameters": {}
        }
        """
        source = config["source"]

        # 1. Select Strategies
        extractor_name = config.get("extractor", "HttpExtractor")
        transformer_name = config.get("transformer", "DOMTransformer")
        loader_name = config.get("loader", "YamlLoader")

        extractor = self.extractors[extractor_name]
        transformer = self.transformers[transformer_name]
        loader = self.loaders[loader_name]

        # 2. Execute Pipeline Sequence
        raw_data = await extractor.extract(
            source,
            parameters=config.get("extractor_parameters")
        )

        transformed_data = transformer.transform(
            raw_data,
            parameters=config.get("transformer_parameters")
        )

        final_payload = loader.serialize(
            transformed_data,
            parameters=config.get("loader_parameters")
        )

        return final_payload
