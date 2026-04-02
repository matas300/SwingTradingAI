from __future__ import annotations

import json
import re
from pathlib import Path

from .constants import DEFAULT_USER_ID
from .repository import SYNC_TABLES
from .storage import SQLiteStore


def _firestore_client(project_id: str):
    try:
        from google.cloud import firestore
    except ImportError as exc:
        raise RuntimeError("google-cloud-firestore is required for Firestore sync") from exc
    return firestore.Client(project=project_id)


def _sqlite_ready_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    return value


def sync_firestore_to_sqlite(*, database_path: str | Path, project_id: str) -> None:
    repository = SQLiteStore(database_path)
    repository.ensure_schema()
    repository.seed_defaults(user_id=DEFAULT_USER_ID)
    client = _firestore_client(project_id)

    with repository.connect() as connection:
        for table in SYNC_TABLES:
            documents = list(client.collection(table).stream())
            if not documents:
                continue
            table_info = connection.execute(f"PRAGMA table_info({table})").fetchall()
            if not table_info:
                continue
            columns = [str(column["name"]) for column in table_info]
            primary_key = next((str(column["name"]) for column in table_info if int(column["pk"])), columns[0])
            for document in documents:
                payload = document.to_dict() or {}
                if primary_key not in payload:
                    payload[primary_key] = document.id
                row = {
                    column: _sqlite_ready_value(payload[column])
                    for column in columns
                    if column in payload
                }
                if not row:
                    continue
                ordered_columns = list(row.keys())
                if not re.match(r"^[a-zA-Z0-9_]+$", table):
                    raise ValueError(f"Invalid table name: {table}")
                for col in ordered_columns:
                    if not re.match(r"^[a-zA-Z0-9_]+$", col):
                        raise ValueError(f"Invalid column name: {col}")
                placeholders = ", ".join("?" for _ in ordered_columns)
                connection.execute(
                    f"INSERT OR REPLACE INTO {table} ({', '.join(ordered_columns)}) VALUES ({placeholders})",
                    tuple(row[column] for column in ordered_columns),
                )
        connection.commit()


def sync_sqlite_to_firestore(*, database_path: str | Path, project_id: str) -> None:
    repository = SQLiteStore(database_path)
    client = _firestore_client(project_id)

    for table in SYNC_TABLES:
        rows = repository.export_table_rows(table)
        if not rows:
            continue
        batch = client.batch()
        pending = 0
        key_name = next(iter(rows[0].keys()))
        for row in rows:
            document_id = str(row[key_name])
            batch.set(client.collection(table).document(document_id), row)
            pending += 1
            if pending >= 300:
                batch.commit()
                batch = client.batch()
                pending = 0
        if pending:
            batch.commit()

    client.collection("_app").document("dashboard").set(
        repository.build_dashboard_bundle(user_id=DEFAULT_USER_ID)
    )
