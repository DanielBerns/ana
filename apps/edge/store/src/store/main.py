import hashlib
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Ana Edge: Store API", version="2.0.0")

class StoreResponse(BaseModel):
    uri: str
    size_bytes: int
    hash_id: str

@app.post("/api/v1/blobs", response_model=StoreResponse)
async def upload_blob(file: UploadFile = File(...)):
    """
    Accepts heavy payloads to support the 'Claim Check' pattern.
    Returns a lightweight URI to be published to the Event Broker.
    """
    try:
        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()

        # NOTE: Outbound Hexagonal Adapter for Disk/S3 saving goes here.
        uri = f"store://blobs/{file_hash}"

        return StoreResponse(
            uri=uri,
            size_bytes=len(content),
            hash_id=file_hash
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to store blob")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "store"}
