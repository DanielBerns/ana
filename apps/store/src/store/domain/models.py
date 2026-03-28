from sqlalchemy import Column, String, Integer, DateTime, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class FileRecord(Base):
    __tablename__ = "store_file_records"

    # SHA-256 hash acts as the primary key for native deduplication
    hash_id = Column(String, primary_key=True)

    original_filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)

    collection_id = Column(String, index=True, nullable=True)
    retention_policy = Column(String, default="standard", nullable=False)

    expires_at = Column(DateTime(timezone=True), index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
