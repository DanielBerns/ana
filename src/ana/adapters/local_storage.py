# ana/adapters/local_storage.py
import json
import uuid
from pathlib import Path
from typing import Any

import aiofiles

from ana.ports.interfaces import ResourceRepositoryPort


class LocalResourceRepository(ResourceRepositoryPort):
    def __init__(self, base_dir: str = "storage/local_repo"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, stream: bytes, metadata: dict[str, Any]) -> str:
        """Saves the stream and metadata, returning a unique URI."""
        resource_id = str(uuid.uuid4())

        file_path = self.base_dir / f"{resource_id}.bin"
        meta_path = self.base_dir / f"{resource_id}.meta.json"

        # Save the binary payload
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(stream)

        # Save the metadata alongside it
        async with aiofiles.open(meta_path, "w") as f:
            await f.write(json.dumps(metadata))

        return f"local://{resource_id}"

    async def fetch(self, resource_uri: str) -> bytes:
        """Fetches the byte stream using the URI."""
        if not resource_uri.startswith("local://"):
            raise ValueError(f"Invalid URI scheme for local storage: {resource_uri}")

        resource_id = resource_uri.replace("local://", "")
        file_path = self.base_dir / f"{resource_id}.bin"

        if not file_path.exists():
            raise FileNotFoundError(f"Resource not found: {resource_uri}")

        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()
