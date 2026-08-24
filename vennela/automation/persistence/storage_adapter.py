from __future__ import annotations

import sqlite3
import json
from typing import Optional, Dict, Any, List
from pathlib import Path


class StorageError(Exception):
    pass


class SQLiteStorageAdapter:
    """Simple SQLite-backed storage adapter for processes.

    Stores process JSON blobs keyed by process_id. Provides optimistic
    version checking (managed by ProcessModel.version).
    """

    def __init__(self, db_path: Optional[str] = None):
        db_path = db_path or (Path.cwd() / "automation_phase1.db").as_posix()
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS processes (process_id TEXT PRIMARY KEY, payload TEXT, version INTEGER, created_at TEXT)"
        )
        self._conn.commit()

    def create(self, process_id: str, payload: Dict[str, Any], version: int) -> None:
        try:
            self._conn.execute(
                "INSERT INTO processes (process_id, payload, version, created_at) VALUES (?, ?, ?, datetime('now'))",
                (process_id, json.dumps(payload), int(version)),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as e:
            raise StorageError(f"Process already exists: {process_id}") from e

    def get(self, process_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT payload, version FROM processes WHERE process_id = ?",
            (process_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        payload, version = row
        obj = json.loads(payload)
        obj["version"] = int(version)
        return obj

    def update(self, process_id: str, payload: Dict[str, Any], expected_version: int) -> None:
        cur = self._conn.execute(
            "SELECT version FROM processes WHERE process_id = ?",
            (process_id,)
        )
        row = cur.fetchone()
        if not row:
            raise StorageError(f"Process not found: {process_id}")
        current_version = int(row[0])
        if current_version != expected_version:
            raise StorageError(f"Version conflict for {process_id}: current={current_version} expected={expected_version}")
        new_version = expected_version + 1
        self._conn.execute(
            "UPDATE processes SET payload = ?, version = ? WHERE process_id = ?",
            (json.dumps(payload), new_version, process_id)
        )
        self._conn.commit()

    def delete(self, process_id: str) -> None:
        self._conn.execute("DELETE FROM processes WHERE process_id = ?", (process_id,))
        self._conn.commit()

    def list(self) -> List[Dict[str, Any]]:
        cur = self._conn.execute("SELECT payload, version FROM processes")
        rows = cur.fetchall()
        results = []
        for payload, version in rows:
            obj = json.loads(payload)
            obj["version"] = int(version)
            results.append(obj)
        return results

    def exists(self, process_id: str) -> bool:
        cur = self._conn.execute("SELECT 1 FROM processes WHERE process_id = ?", (process_id,))
        return cur.fetchone() is not None
