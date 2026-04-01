from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="Ana Edge: Scraper API", version="2.0.0")

class ScrapeRequest(BaseModel):
    url: HttpUrl

class ScrapeResponse(BaseModel):
    url: str
    title: str
    content: str
    status: str = "success"

@app.post("/api/v1/scrape", response_model=ScrapeResponse)
async def scrape_url(request: ScrapeRequest):
    """
    Synchronous HTTP API to scrape a target URL.
    This replaces the embedded ScrapingEventSource logic from v1.0.
    """
    try:
        # NOTE: Domain logic would go here (e.g., using httpx and BeautifulSoup).
        # We mock the return for the architectural baseline.
        return ScrapeResponse(
            url=str(request.url),
            title="Mock Extracted Title",
            content="Mock scraped content from the isolated edge boundary."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "scraper"}
