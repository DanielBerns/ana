from fastapi.testclient import TestClient
from scraper.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_scrape_endpoint_success():
    payload = {"url": "https://example.com"}
    response = client.post("/api/v1/scrape", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://example.com/"
    assert "content" in data
    assert data["status"] == "success"

def test_scrape_endpoint_invalid_url():
    payload = {"url": "not-a-valid-url"}
    response = client.post("/api/v1/scrape", json=payload)

    assert response.status_code == 422 # FastAPI validation error
