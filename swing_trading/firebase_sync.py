from __future__ import annotations

from pathlib import Path

from .storage import SQLiteStore

TABLES = (
    "users",
    "watched_tickers",
    "ticker_daily_snapshots",
    "ticker_profiles",
    "model_features",
    "predictions",
    "targets",
    "signal_history",
    "backtest_runs",
    "ui_preferences",
)


def sync_sqlite_to_firestore(
    *,
    database_path: str | Path,
    project_id: str,
) -> None:
    try:
        from google.cloud import firestore
    except ImportError as exc:
        raise RuntimeError("google-cloud-firestore is required for Firestore sync") from exc

    store = SQLiteStore(database_path)
    client = firestore.Client(project=project_id)

    for table in TABLES:
        rows = store.export_table_rows(table)
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
