"""Small SQLite store for submitted runs and review status."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    model_key TEXT NOT NULL,
    model_name TEXT NOT NULL,
    lab TEXT NOT NULL,
    dataset_sha256 TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    model_json TEXT NOT NULL,
    predictions_json TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_submissions_model ON submissions(model_key);
CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_submission(
    path: Path | str,
    *,
    model: dict[str, Any],
    dataset_sha256: str,
    summary: dict[str, Any],
    predictions: list[dict[str, Any]],
    notes: str = "",
) -> int:
    with connect(path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO submissions
            (created_at, status, model_key, model_name, lab, dataset_sha256,
             summary_json, model_json, predictions_json, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now(),
                "pending",
                str(model.get("key", "unknown")),
                str(model.get("name", "unknown")),
                str(model.get("lab", "unknown")),
                dataset_sha256,
                json.dumps(summary, sort_keys=True),
                json.dumps(model, sort_keys=True),
                json.dumps(predictions, sort_keys=True),
                notes,
            ),
        )
        return int(cursor.lastrowid)


def list_submissions(path: Path | str, status: str | None = None) -> list[dict[str, Any]]:
    query = "SELECT id, created_at, status, model_key, model_name, lab, dataset_sha256, summary_json, notes FROM submissions"
    params: tuple[Any, ...] = ()
    if status:
        query += " WHERE status = ?"
        params = (status,)
    query += " ORDER BY id DESC"
    with connect(path) as connection:
        rows = connection.execute(query, params).fetchall()
    output = []
    for row in rows:
        data = dict(row)
        data["summary"] = json.loads(data.pop("summary_json"))
        output.append(data)
    return output


def get_submission(path: Path | str, submission_id: int) -> dict[str, Any] | None:
    with connect(path) as connection:
        row = connection.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["summary"] = json.loads(data.pop("summary_json"))
    data["model"] = json.loads(data.pop("model_json"))
    data["predictions"] = json.loads(data.pop("predictions_json"))
    return data


def update_status(path: Path | str, submission_id: int, status: str) -> bool:
    with connect(path) as connection:
        cursor = connection.execute(
            "UPDATE submissions SET status = ? WHERE id = ?", (status, submission_id)
        )
        return cursor.rowcount > 0
