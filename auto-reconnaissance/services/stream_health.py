"""Track entity freshness from the Lattice entity stream."""

from __future__ import annotations

from datetime import datetime, timezone


class EntityStreamHealth:
    """Records last-seen timestamps for streamed entities."""

    def __init__(self) -> None:
        self._last_seen: dict[str, datetime] = {}

    def record(self, entity_id: str, seen_at: datetime | None = None) -> None:
        self._last_seen[entity_id] = seen_at or datetime.now(timezone.utc)

    def seconds_since(self, entity_id: str, now: datetime | None = None) -> float | None:
        seen = self._last_seen.get(entity_id)
        if seen is None:
            return None
        current = now or datetime.now(timezone.utc)
        return (current - seen).total_seconds()

    def is_stale(self, entity_id: str, max_stale_seconds: float, now: datetime | None = None) -> bool:
        gap = self.seconds_since(entity_id, now)
        if gap is None:
            return True
        return gap > max_stale_seconds
