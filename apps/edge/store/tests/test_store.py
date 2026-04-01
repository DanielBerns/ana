from fastapi.testclient import TestClient
from store.main import app

client = TestClient(app)

def test_upload_blob():
    # Simulate a file upload
    file_content = b"This is a heavy payload representing scraped data."
    files = {"file": ("test_payload.txt", file_content, "text/plain")}

    response = client.post("/api/v1/blobs", files=files)

    assert response.status_code == 200
    data = response.json()

    assert "uri" in data
    assert data["uri"].startswith("store://blobs/")
    assert data["size_bytes"] == len(file_content)
    assert "hash_id" in data
