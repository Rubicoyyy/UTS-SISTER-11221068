import sqlite3
import threading
import os
from typing import List, Optional, Dict, Any


class DedupStore:
    def __init__(self, db_path: str = "./data/dedup.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None

    def init_db(self):
        with self._lock:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    topic TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    timestamp TEXT,
                    source TEXT,
                    payload TEXT,
                    PRIMARY KEY (topic, event_id)
                )
                """
            )
            self._conn.commit()

    def record_event(self, topic: str, event_id: str, timestamp: str, source: str, payload: Dict[str, Any]) -> bool:
        """Try to record. Return True if new, False if duplicate."""
        with self._lock:
            try:
                cur = self._conn.cursor()
                cur.execute(
                    "INSERT INTO events (topic, event_id, timestamp, source, payload) VALUES (?, ?, ?, ?, ?)",
                    (topic, event_id, timestamp, source, str(payload)),
                )
                self._conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def list_events(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            if topic:
                cur.execute("SELECT topic,event_id,timestamp,source,payload FROM events WHERE topic = ? ORDER BY rowid", (topic,))
            else:
                cur.execute("SELECT topic,event_id,timestamp,source,payload FROM events ORDER BY rowid")
            rows = cur.fetchall()
            return [
                {
                    "topic": r[0],
                    "event_id": r[1],
                    "timestamp": r[2],
                    "source": r[3],
                    "payload": r[4],
                }
                for r in rows
            ]

    def list_topics(self) -> List[str]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT DISTINCT topic FROM events")
            return [r[0] for r in cur.fetchall()]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
