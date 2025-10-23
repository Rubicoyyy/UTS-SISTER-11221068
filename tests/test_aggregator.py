import os
import tempfile
import shutil
import time
import asyncio
import sqlite3
from fastapi.testclient import TestClient

from src.main import create_app
from src.dedup import DedupStore


def test_dedup_basic(tmp_path):
    db = tmp_path / "dedup.db"
    app = create_app(str(db))
    client = TestClient(app)
    with client:
        # publish single
        ev = {"topic": "t1", "event_id": "e1", "timestamp": "2025-10-24T00:00:00Z", "source": "test", "payload": {}}
        r = client.post("/publish", json=ev)
        assert r.status_code == 200
        time.sleep(0.1)
        events = client.get("/events").json()
        assert any(e["event_id"] == "e1" for e in events)
        # publish duplicate
        r2 = client.post("/publish", json=ev)
        assert r2.status_code == 200
        time.sleep(0.1)
        # duplicates should not increase stored events
        events2 = client.get("/events").json()
        assert len(events2) == len(events)


def test_persistence(tmp_path):
    db = tmp_path / "dedup.db"
    store = DedupStore(str(db))
    store.init_db()
    store.record_event("t2", "e2", "2025-10-24T00:00:00Z", "test", {})
    store.close()

    # reopen new instance
    store2 = DedupStore(str(db))
    store2.init_db()
    assert store2.record_event("t2", "e2", "2025-10-24T00:00:00Z", "test", {}) is False


def test_schema_and_stats(tmp_path):
    db = tmp_path / "dedup.db"
    app = create_app(str(db))
    client = TestClient(app)
    with client:
        ev = {"topic": "t3", "event_id": "e3", "timestamp": "2025-10-24T00:00:00Z", "source": "s", "payload": {}}
        client.post("/publish", json=ev)
        time.sleep(0.1)
        events = client.get("/events").json()
        assert any(e["event_id"] == "e3" for e in events)
        stats = client.get("/stats").json()
        assert "received" in stats and "unique_processed" in stats


def test_small_stress(tmp_path):
    db = tmp_path / "dedup.db"
    store = DedupStore(str(db))
    store.init_db()
    n = 1000
    start = time.time()
    for i in range(n):
        store.record_event("stress", f"id-{i//2}", "2025-10-24T00:00:00Z", "s", {})
    duration = time.time() - start
    # many duplicates because id repeats; ensure runs quickly
    assert duration < 5.0


def test_batch_publish_and_stats(tmp_path):
    db = tmp_path / "dedup.db"
    app = create_app(str(db))
    client = TestClient(app)
    with client:
        # create batch with duplicates
        events = []
        for i in range(200):
            events.append({"topic": "batch", "event_id": f"id-{i%160}", "timestamp": "2025-10-24T00:00:00Z", "source": "t", "payload": {}})
        r = client.post("/publish", json=events)
        assert r.status_code == 200
        time.sleep(0.2)
        stats = client.get("/stats").json()
        # received should be 200 (enqueued), unique_processed <=200 and duplicates dropped >0
        assert stats["received"] >= 200
        assert stats["unique_processed"] + stats["duplicate_dropped"] >= 200
