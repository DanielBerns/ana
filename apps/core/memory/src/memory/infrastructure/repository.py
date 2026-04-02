from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..domain.models import EventLog, Entity, Triple

class MemoryRepository:
    """Outbound adapter for persisting and retrieving state from PostgreSQL."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_event(self, correlation_id: str, event_type: str, payload: dict) -> None:
        """Deterministically archives an event payload."""
        new_log = EventLog(
            correlation_id=correlation_id,
            event_type=event_type,
            payload=payload
        )
        self.session.add(new_log)
        await self.session.commit()

    async def get_recent_history(self, limit: int = 5) -> list[dict]:
        """Fetches the most recent chronological events to build context."""
        stmt = select(EventLog).order_by(EventLog.timestamp.desc()).limit(limit)
        result = await self.session.execute(stmt)

        # We reverse the result so it reads chronologically (oldest to newest)
        logs = [row.payload for row in result.scalars()]
        logs.reverse()
        return logs
