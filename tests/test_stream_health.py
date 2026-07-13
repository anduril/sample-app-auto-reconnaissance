import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "auto-reconnaissance"))

from services.stream_health import EntityStreamHealth  # noqa: E402


class EntityStreamHealthTest(unittest.TestCase):
    def test_fresh_entity_not_stale(self):
        health = EntityStreamHealth()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        health.record("asset-1", now)
        self.assertFalse(health.is_stale("asset-1", 120, now + timedelta(seconds=30)))

    def test_old_entity_is_stale(self):
        health = EntityStreamHealth()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        health.record("track-1", now)
        self.assertTrue(health.is_stale("track-1", 60, now + timedelta(seconds=61)))

    def test_never_seen_is_stale(self):
        health = EntityStreamHealth()
        self.assertTrue(health.is_stale("missing", 10))


if __name__ == "__main__":
    unittest.main()
