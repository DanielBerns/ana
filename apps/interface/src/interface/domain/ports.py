from typing import Protocol

class ScrapingClient(Protocol):
    """The Port: Defines how the system interacts with the target web pages."""
    async def fetch_html(self, url: str) -> str:
        """Navigates to the URL and returns the fully rendered HTML payload."""
        ...

    async def close(self) -> None:
        """Cleans up the client/browser session."""
        ...
