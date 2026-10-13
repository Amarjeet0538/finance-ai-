"""SQLite-backed Event Bus for IPC between Agent, UI, and Human Approval gates."""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPORTS_DIR = Path("reports")


def get_db_path(run_id: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR / f"events_{run_id}.db"


def init_event_bus(run_id: str) -> None:
    """Initialize SQLite database for the run with WAL mode."""
    db_path = get_db_path(run_id)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_run_id ON events (run_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events (type);")
        conn.commit()
    finally:
        conn.close()


def emit(run_id: str, event_type: str, payload: Dict[str, Any]) -> int:
    """Emit an event row into the run's events SQLite database."""
    init_event_bus(run_id)
    db_path = get_db_path(run_id)
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    try:
        ts = datetime.now(timezone.utc).isoformat()
        payload_str = json.dumps(payload)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (run_id, timestamp, type, payload_json) VALUES (?, ?, ?, ?)",
            (run_id, ts, event_type, payload_str),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def poll_events(
    run_id: str,
    since_id: int = 0,
    type_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Poll for events since a given ID, optionally filtering by type."""
    db_path = get_db_path(run_id)
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        if type_filter:
            cursor.execute(
                "SELECT id, run_id, timestamp, type, payload_json FROM events WHERE run_id = ? AND id > ? AND type = ? ORDER BY id ASC",
                (run_id, since_id, type_filter),
            )
        else:
            cursor.execute(
                "SELECT id, run_id, timestamp, type, payload_json FROM events WHERE run_id = ? AND id > ? ORDER BY id ASC",
                (run_id, since_id),
            )
        rows = cursor.fetchall()
        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "run_id": r["run_id"],
                "timestamp": r["timestamp"],
                "type": r["type"],
                "payload": json.loads(r["payload_json"]),
            })
        return results
    finally:
        conn.close()
