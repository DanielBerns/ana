import os
from typing import Protocol

class StorageProvider(Protocol):
    async def put(self, temp_filepath: str, hash_id: str) -> None:
        """Moves a temporary file into permanent storage using its hash as the name."""
        ...

    async def get_path(self, hash_id: str) -> str:
        """Returns the physical or virtual path to the file."""
        ...

    async def delete(self, hash_id: str) -> bool:
        """Physically removes the file."""
        ...

class LocalStorageAdapter:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    async def put(self, temp_filepath: str, hash_id: str) -> None:
        target_path = os.path.join(self.base_dir, hash_id)
        # Content-Addressable Storage: If the file already exists, we do nothing!
        if not os.path.exists(target_path):
            os.rename(temp_filepath, target_path)
        else:
            os.remove(temp_filepath)

    async def get_path(self, hash_id: str) -> str:
        return os.path.join(self.base_dir, hash_id)

    async def delete(self, hash_id: str) -> bool:
        target_path = os.path.join(self.base_dir, hash_id)
        if os.path.exists(target_path):
            os.remove(target_path)
            return True
        return False
