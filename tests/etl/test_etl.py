# tests/edge-etl/test_etl.py
import pytest
from unittest.mock import patch, mock_open
from etl.domain.extractors import HttpExtractor, FileSystemExtractor
from etl.domain.transformers import DOMTransformer, RegexTransformer
from etl.domain.pipeline import ETLPipeline

# --- 1. Extractor Tests (Mocking Infrastructure) ---

@pytest.mark.asyncio
async def test_http_extractor_success(httpx_mock):
    # Arrange: Intercept the HTTP call
    url = "https://example.com/weather"
    httpx_mock.add_response(url=url, text="<html>Weather Data</html>")
    extractor = HttpExtractor()

    # Act
    result = await extractor.extract(url)

    # Assert
    assert result["content"] == "<html>Weather Data</html>"

@pytest.mark.asyncio
async def test_filesystem_extractor_reads_local_file():
    # Arrange: Mock reading a raw WhatsApp chat export file from a local volume
    fake_file_path = "/data/chats/chat_export.txt"
    fake_content = "[14/10/25, 10:00:00] Operator: System diagnostic check."
    extractor = FileSystemExtractor()

    # Act & Assert
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=fake_content)):
            result = await extractor.extract(fake_file_path)

    assert result["content"] == fake_content

# --- 2. Transformer Tests (Pure Offline Logic) ---

def test_dom_transformer_extracts_price_reports():
    # Arrange: Mock a dynamic storefront for shopping list price reports
    html_payload = {
        "content": """
        <div class="product-list">
            <div class="item"><span class="price">$15.99</span></div>
            <div class="item"><span class="price">$4.50</span></div>
        </div>
        """
    }
    transformer = DOMTransformer()

    # Act: Target the price elements
    result = transformer.transform(html_payload, target_selector=".price")

    # Assert
    assert len(result) == 2
    assert result[0]["text"] == "$15.99"
    assert result[1]["text"] == "$4.50"

def test_regex_transformer_extracts_patterns():
    # Arrange: A raw text payload
    text_payload = {"content": "Error code: 404 Not Found. Error code: 500 Internal."}
    transformer = RegexTransformer()

    # Act: Extract numeric codes
    result = transformer.transform(text_payload, pattern=r"Error code: (\d+)")

    # Assert
    assert len(result) == 2
    assert result[0]["groups"] == ("404",)
    assert result[1]["groups"] == ("500",)

# --- 3. Pipeline Factory Tests ---

@pytest.mark.asyncio
async def test_etl_pipeline_end_to_end(httpx_mock):
    # Arrange: Mock a webpage being scraped for news
    url = "https://example.com/news_weaver/latest"
    mock_html = "<html><body><article>New release deployed</article><article>System stable</article></body></html>"
    httpx_mock.add_response(url=url, text=mock_html)

    pipeline = ETLPipeline()
    config = {
        "source": url,
        "extractor": "HttpExtractor",
        "transformer": "DOMTransformer",
        "loader": "YamlLoader",
        "transformer_kwargs": {"target_selector": "article"}
    }

    # Act
    yaml_output = await pipeline.execute(config)

    # Assert: Verify the full E -> T -> L flow output
    assert "- text: New release deployed" in yaml_output
    assert "- text: System stable" in yaml_output
