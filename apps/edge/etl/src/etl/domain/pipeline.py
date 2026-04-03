from .extractors import HttpExtractor, SeleniumExtractor, FileSystemExtractor, ApiExtractor
from .transformers import DOMTransformer, RegexTransformer, JSONPathTransformer
from .loaders import YamlLoader, CsvLoader

class ETLPipeline:
    """Dynamically constructs and executes a data pipeline based on configuration."""

    def __init__(self):
        # The Registry of available strategies
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

    async def execute(self, config: dict) -> str:
        """
        Executes the E -> T -> L sequence.
        Expected config format:
        {
            "source": "https://...",
            "extractor": "HttpExtractor",
            "transformer": "DOMTransformer",
            "loader": "YamlLoader",
            "extractor_kwargs": {},
            "transformer_kwargs": {"target_selector": "article"},
            "loader_kwargs": {}
        }
        """
        source = config["source"]

        # 1. Select Strategies (Defaulting to the most common web-scraping setup)
        e_name = config.get("extractor", "HttpExtractor")
        t_name = config.get("transformer", "DOMTransformer")
        l_name = config.get("loader", "YamlLoader")

        extractor = self.extractors[e_name]
        transformer = self.transformers[t_name]
        loader = self.loaders[l_name]

        # 2. Execute Pipeline Sequence
        raw_data = await extractor.extract(source, **config.get("extractor_kwargs", {}))
        transformed_data = transformer.transform(raw_data, **config.get("transformer_kwargs", {}))
        final_payload = loader.serialize(transformed_data, **config.get("loader_kwargs", {}))

        return final_payload
