from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class PersonState:
    immich_person_id: str
    immich_name: str
    frigate_name: str
    active: bool
    created_by_bridge: bool


class StateStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.migrate()

    def close(self) -> None:
        self.conn.close()

    def migrate(self) -> None:
        self.conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS people (
              immich_person_id TEXT PRIMARY KEY,
              immich_name TEXT NOT NULL,
              frigate_name TEXT NOT NULL UNIQUE,
              active INTEGER NOT NULL,
              first_seen TEXT NOT NULL,
              last_seen TEXT NOT NULL,
              last_sync TEXT,
              created_by_bridge INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS faces (
              immich_face_id TEXT PRIMARY KEY,
              immich_person_id TEXT NOT NULL,
              immich_asset_id TEXT NOT NULL,
              content_hash TEXT NOT NULL UNIQUE,
              frigate_name TEXT NOT NULL,
              quality_score REAL NOT NULL,
              synced_at TEXT NOT NULL,
              FOREIGN KEY (immich_person_id) REFERENCES people(immich_person_id)
            );
            CREATE INDEX IF NOT EXISTS faces_person_idx ON faces(immich_person_id);
            """
        )
        self.conn.commit()

    def people(self) -> list[PersonState]:
        rows = self.conn.execute("SELECT * FROM people").fetchall()
        return [
            PersonState(
                immich_person_id=row["immich_person_id"],
                immich_name=row["immich_name"],
                frigate_name=row["frigate_name"],
                active=bool(row["active"]),
                created_by_bridge=bool(row["created_by_bridge"]),
            )
            for row in rows
        ]

    def get_person(self, person_id: str) -> PersonState | None:
        row = self.conn.execute(
            "SELECT * FROM people WHERE immich_person_id = ?", (person_id,)
        ).fetchone()
        if row is None:
            return None
        return PersonState(
            row["immich_person_id"],
            row["immich_name"],
            row["frigate_name"],
            bool(row["active"]),
            bool(row["created_by_bridge"]),
        )

    def upsert_person(self, person_id: str, name: str, frigate_name: str, active: bool) -> None:
        stamp = now_iso()
        self.conn.execute(
            """
            INSERT INTO people
              (immich_person_id, immich_name, frigate_name, active, first_seen, last_seen,
               created_by_bridge)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(immich_person_id) DO UPDATE SET
              immich_name=excluded.immich_name,
              active=excluded.active,
              last_seen=excluded.last_seen
            """,
            (person_id, name, frigate_name, int(active), stamp, stamp),
        )
        self.conn.commit()

    def mark_seen_inactive(self, person_id: str, name: str) -> None:
        stamp = now_iso()
        self.conn.execute(
            """
            UPDATE people SET immich_name = ?, active = 0, last_seen = ?
            WHERE immich_person_id = ?
            """,
            (name, stamp, person_id),
        )
        self.conn.commit()

    def mark_person_synced(self, person_id: str) -> None:
        self.conn.execute(
            "UPDATE people SET last_sync = ? WHERE immich_person_id = ?", (now_iso(), person_id)
        )
        self.conn.commit()

    def synced_face_ids(self, person_id: str) -> set[str]:
        rows = self.conn.execute(
            "SELECT immich_face_id FROM faces WHERE immich_person_id = ?", (person_id,)
        ).fetchall()
        return {row["immich_face_id"] for row in rows}

    def synced_count(self, person_id: str) -> int:
        row = self.conn.execute(
            "SELECT count(*) AS count FROM faces WHERE immich_person_id = ?", (person_id,)
        ).fetchone()
        return int(row["count"])

    def has_content_hash(self, content_hash: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM faces WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return row is not None

    def record_face(
        self,
        *,
        face_id: str,
        person_id: str,
        asset_id: str,
        content_hash: str,
        frigate_name: str,
        quality_score: float,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO faces
              (immich_face_id, immich_person_id, immich_asset_id, content_hash,
               frigate_name, quality_score, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (face_id, person_id, asset_id, content_hash, frigate_name, quality_score, now_iso()),
        )
        self.conn.commit()
