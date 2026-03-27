from __future__ import annotations

import argparse
import os

from swing_trading.firebase_sync import sync_sqlite_to_firestore
from swing_trading.service import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the daily SwingTradingAI refresh pipeline.")
    parser.add_argument("--daily-period", default="2y")
    parser.add_argument("--no-firestore-sync", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_pipeline(daily_period=args.daily_period)
    print(f"Run {result['run_id']} completed for {result['saved_tickers']} tickers")
    if result["failures"]:
        print("Failures:")
        for item in result["failures"]:
            print(f"- {item}")

    project_id = os.getenv("FIREBASE_PROJECT_ID")
    if not args.no_firestore_sync and project_id:
        sync_sqlite_to_firestore(
            database_path=os.getenv("DATABASE_PATH", "history/swing_trading_ai.sqlite3"),
            project_id=project_id,
        )
        print("Firestore sync completed")


if __name__ == "__main__":
    main()
