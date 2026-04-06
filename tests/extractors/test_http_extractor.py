import pytest
import httpx

# Adjust this import to match your project structure
from etl.domain.extractors import HttpExtractor

@pytest.mark.asyncio
async def test_http_extractor_real_network_integration():
    test_url = "https://example.com"
    extractor = HttpExtractor()

    # Act: Pass verify=False to bypass your local machine's broken SSL chain
    result = await extractor.extract(test_url, verify=False)

    assert "content" in result
    assert isinstance(result["content"], str)
    assert "Example Domain" in result["content"]

@pytest.mark.asyncio
async def test_http_extractor_real_network_not_found():
    test_url = "https://example.com/this-page-definitely-does-not-exist-12345"
    extractor = HttpExtractor()

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await extractor.extract(test_url, verify=False)

    assert exc_info.value.response.status_code == 404

