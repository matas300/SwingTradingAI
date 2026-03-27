from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .constants import DEFAULT_TICKERS, DEFAULT_USER_ID, DEFAULT_USER_NAME
from .models import FeatureSnapshot, PredictionRecord, SignalOutcome, TargetLevel, TickerPipelineResult


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


class SQLiteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterable[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def ensure_schema(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                email TEXT,
                is_demo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS watched_tickers (
                watch_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                label TEXT,
                notes TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, ticker),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_watched_tickers_user_active
            ON watched_tickers(user_id, is_active)
            """,
            """
            CREATE TABLE IF NOT EXISTS ticker_daily_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                session_date TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                atr REAL NOT NULL,
                adx REAL NOT NULL,
                rsi REAL NOT NULL,
                support REAL,
                resistance REAL,
                trend TEXT NOT NULL,
                market_regime TEXT NOT NULL,
                drawdown_63d REAL NOT NULL,
                relative_strength_1m REAL NOT NULL,
                volatility_20d REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(ticker, session_date)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_snapshots_ticker_date
            ON ticker_daily_snapshots(ticker, session_date DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS model_features (
                feature_id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                session_date TEXT NOT NULL,
                feature_set TEXT NOT NULL,
                features_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(ticker, session_date, feature_set)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_model_features_ticker_date
            ON model_features(ticker, session_date DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                session_date TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_low REAL,
                entry_high REAL,
                stop_loss REAL,
                confidence_score REAL NOT NULL,
                risk_reward REAL,
                holding_horizon_days INTEGER NOT NULL,
                regime TEXT NOT NULL,
                reliability_label TEXT NOT NULL,
                rationale_json TEXT NOT NULL,
                warning_flags_json TEXT NOT NULL,
                top_factors_json TEXT NOT NULL,
                profile_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(ticker, session_date)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_predictions_ticker_date
            ON predictions(ticker, session_date DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS targets (
                target_id TEXT PRIMARY KEY,
                prediction_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                price REAL NOT NULL,
                probability REAL,
                distance_atr REAL NOT NULL,
                rationale TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(prediction_id, kind),
                FOREIGN KEY(prediction_id) REFERENCES predictions(prediction_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS signal_history (
                signal_id TEXT PRIMARY KEY,
                prediction_id TEXT NOT NULL UNIQUE,
                ticker TEXT NOT NULL,
                session_date TEXT NOT NULL,
                direction TEXT NOT NULL,
                regime TEXT NOT NULL,
                outcome_status TEXT NOT NULL,
                target_1_hit INTEGER NOT NULL,
                target_2_hit INTEGER NOT NULL,
                stop_hit INTEGER NOT NULL,
                max_adverse_excursion REAL NOT NULL,
                max_favorable_excursion REAL NOT NULL,
                realized_return_pct REAL NOT NULL,
                holding_days INTEGER NOT NULL,
                target_error REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(prediction_id) REFERENCES predictions(prediction_id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_signal_history_ticker_date
            ON signal_history(ticker, session_date DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS ticker_profiles (
                profile_id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL UNIQUE,
                sample_size INTEGER NOT NULL,
                closed_signal_count INTEGER NOT NULL,
                long_win_rate REAL NOT NULL,
                short_win_rate REAL NOT NULL,
                volatility_rolling REAL NOT NULL,
                atr_rolling REAL NOT NULL,
                recent_drawdown REAL NOT NULL,
                mean_target_error REAL NOT NULL,
                mean_mae REAL NOT NULL,
                mean_mfe REAL NOT NULL,
                avg_days_to_target REAL,
                avg_days_to_stop REAL,
                long_effectiveness REAL NOT NULL,
                short_effectiveness REAL NOT NULL,
                dominant_regime TEXT NOT NULL,
                confidence_floor REAL NOT NULL,
                target_aggression REAL NOT NULL,
                target_shrink_factor REAL NOT NULL,
                reliability_score REAL NOT NULL,
                insufficient_data INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_ticker_profiles_reliability
            ON ticker_profiles(reliability_score DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS backtest_runs (
                run_id TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                configuration_json TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS ui_preferences (
                preference_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL UNIQUE,
                theme TEXT NOT NULL,
                density TEXT NOT NULL,
                default_view TEXT NOT NULL,
                favorite_metric TEXT NOT NULL,
                preferences_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
            """,
        ]

        with self.connect() as connection:
            for statement in statements:
                connection.execute(statement)
            connection.commit()

    def seed_defaults(self, user_id: str = DEFAULT_USER_ID, tickers: tuple[str, ...] = DEFAULT_TICKERS) -> None:
        created_at = now_iso()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO users (user_id, display_name, email, is_demo, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (user_id, DEFAULT_USER_NAME, None, created_at, created_at),
            )
            connection.execute(
                """
                INSERT INTO ui_preferences (
                    preference_id, user_id, theme, density, default_view, favorite_metric,
                    preferences_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (
                    f"prefs:{user_id}",
                    user_id,
                    "system",
                    "comfortable",
                    "overview",
                    "confidence",
                    json_dumps({"theme": "system", "density": "comfortable"}),
                    created_at,
                    created_at,
                ),
            )
            for ticker in tickers:
                connection.execute(
                    """
                    INSERT INTO watched_tickers (watch_id, user_id, ticker, label, notes, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(user_id, ticker) DO UPDATE SET is_active = 1, updated_at = excluded.updated_at
                    """,
                    (f"{user_id}:{ticker}", user_id, ticker, None, None, created_at, created_at),
                )
            connection.commit()

    def replace_watchlist(self, tickers: list[str], user_id: str = DEFAULT_USER_ID) -> None:
        updated_at = now_iso()
        normalized = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
        with self.connect() as connection:
            connection.execute(
                "UPDATE watched_tickers SET is_active = 0, updated_at = ? WHERE user_id = ?",
                (updated_at, user_id),
            )
            for ticker in normalized:
                connection.execute(
                    """
                    INSERT INTO watched_tickers (watch_id, user_id, ticker, label, notes, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(user_id, ticker) DO UPDATE SET is_active = 1, updated_at = excluded.updated_at
                    """,
                    (f"{user_id}:{ticker}", user_id, ticker, None, None, updated_at, updated_at),
                )
            connection.commit()

    def list_active_tickers(self, user_id: str = DEFAULT_USER_ID) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT ticker
                FROM watched_tickers
                WHERE user_id = ? AND is_active = 1
                ORDER BY ticker
                """,
                (user_id,),
            ).fetchall()
        return [str(row["ticker"]) for row in rows]

    def save_pipeline_run(
        self,
        *,
        run_id: str,
        tickers: list[str],
        results: list[TickerPipelineResult],
        generated_at: str,
        config_payload: dict[str, Any],
        market_context: dict[str, Any],
    ) -> None:
        with self.connect() as connection:
            for result in results:
                self._save_result(connection, result, generated_at)
            summary = {
                "ticker_count": len(tickers),
                "actionable_count": sum(1 for result in results if result.latest_prediction.direction != "neutral"),
                "generated_at": generated_at,
                "market_context": market_context,
            }
            connection.execute(
                """
                INSERT INTO backtest_runs (
                    run_id, scope, configuration_json, summary_json, started_at, completed_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    summary_json = excluded.summary_json,
                    completed_at = excluded.completed_at,
                    updated_at = excluded.updated_at
                """,
                (
                    run_id,
                    "daily_refresh",
                    json_dumps(config_payload),
                    json_dumps(summary),
                    generated_at,
                    generated_at,
                    generated_at,
                    generated_at,
                ),
            )
            connection.commit()

    def _save_result(self, connection: sqlite3.Connection, result: TickerPipelineResult, generated_at: str) -> None:
        profile = result.profile
        connection.execute(
            """
            INSERT INTO ticker_profiles (
                profile_id, ticker, sample_size, closed_signal_count, long_win_rate, short_win_rate,
                volatility_rolling, atr_rolling, recent_drawdown, mean_target_error, mean_mae, mean_mfe,
                avg_days_to_target, avg_days_to_stop, long_effectiveness, short_effectiveness,
                dominant_regime, confidence_floor, target_aggression, target_shrink_factor,
                reliability_score, insufficient_data, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                sample_size = excluded.sample_size,
                closed_signal_count = excluded.closed_signal_count,
                long_win_rate = excluded.long_win_rate,
                short_win_rate = excluded.short_win_rate,
                volatility_rolling = excluded.volatility_rolling,
                atr_rolling = excluded.atr_rolling,
                recent_drawdown = excluded.recent_drawdown,
                mean_target_error = excluded.mean_target_error,
                mean_mae = excluded.mean_mae,
                mean_mfe = excluded.mean_mfe,
                avg_days_to_target = excluded.avg_days_to_target,
                avg_days_to_stop = excluded.avg_days_to_stop,
                long_effectiveness = excluded.long_effectiveness,
                short_effectiveness = excluded.short_effectiveness,
                dominant_regime = excluded.dominant_regime,
                confidence_floor = excluded.confidence_floor,
                target_aggression = excluded.target_aggression,
                target_shrink_factor = excluded.target_shrink_factor,
                reliability_score = excluded.reliability_score,
                insufficient_data = excluded.insufficient_data,
                updated_at = excluded.updated_at
            """,
            (
                f"profile:{profile.ticker}",
                profile.ticker,
                profile.sample_size,
                profile.closed_signal_count,
                profile.long_win_rate,
                profile.short_win_rate,
                profile.volatility_rolling,
                profile.atr_rolling,
                profile.recent_drawdown,
                profile.mean_target_error,
                profile.mean_mae,
                profile.mean_mfe,
                profile.avg_days_to_target,
                profile.avg_days_to_stop,
                profile.long_effectiveness,
                profile.short_effectiveness,
                profile.dominant_regime,
                profile.confidence_floor,
                profile.target_aggression,
                profile.target_shrink_factor,
                profile.reliability_score,
                int(profile.insufficient_data),
                generated_at,
                generated_at,
            ),
        )
        for snapshot in result.snapshots:
            self._upsert_snapshot(connection, snapshot, generated_at)
        for prediction in result.historical_predictions:
            self._upsert_prediction(connection, prediction, generated_at)
            for target in result.historical_targets.get(prediction.prediction_id, []):
                self._upsert_target(connection, prediction.prediction_id, target, generated_at)
        for history_row in result.signal_history:
            self._upsert_signal_history(connection, history_row, generated_at)

    def _upsert_snapshot(self, connection: sqlite3.Connection, snapshot: FeatureSnapshot, generated_at: str) -> None:
        connection.execute(
            """
            INSERT INTO ticker_daily_snapshots (
                snapshot_id, ticker, session_date, open, high, low, close, volume, atr, adx, rsi,
                support, resistance, trend, market_regime, drawdown_63d, relative_strength_1m,
                volatility_20d, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, session_date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                atr = excluded.atr,
                adx = excluded.adx,
                rsi = excluded.rsi,
                support = excluded.support,
                resistance = excluded.resistance,
                trend = excluded.trend,
                market_regime = excluded.market_regime,
                drawdown_63d = excluded.drawdown_63d,
                relative_strength_1m = excluded.relative_strength_1m,
                volatility_20d = excluded.volatility_20d,
                updated_at = excluded.updated_at
            """,
            (
                f"{snapshot.ticker}:{snapshot.session_date.isoformat()}",
                snapshot.ticker,
                snapshot.session_date.isoformat(),
                snapshot.open,
                snapshot.high,
                snapshot.low,
                snapshot.close,
                snapshot.volume,
                snapshot.atr,
                snapshot.adx,
                snapshot.rsi,
                snapshot.support,
                snapshot.resistance,
                snapshot.trend,
                snapshot.market_regime,
                snapshot.drawdown_63d,
                snapshot.relative_strength_1m,
                snapshot.volatility_20d,
                generated_at,
                generated_at,
            ),
        )
        connection.execute(
            """
            INSERT INTO model_features (feature_id, ticker, session_date, feature_set, features_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, session_date, feature_set) DO UPDATE SET
                features_json = excluded.features_json,
                updated_at = excluded.updated_at
            """,
            (
                f"{snapshot.ticker}:{snapshot.session_date.isoformat()}:daily_core",
                snapshot.ticker,
                snapshot.session_date.isoformat(),
                "daily_core",
                json_dumps(snapshot.as_dict()),
                generated_at,
                generated_at,
            ),
        )

    def _upsert_prediction(self, connection: sqlite3.Connection, prediction: PredictionRecord, generated_at: str) -> None:
        connection.execute(
            """
            INSERT INTO predictions (
                prediction_id, ticker, session_date, direction, entry_low, entry_high, stop_loss,
                confidence_score, risk_reward, holding_horizon_days, regime, reliability_label,
                rationale_json, warning_flags_json, top_factors_json, profile_version, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, session_date) DO UPDATE SET
                direction = excluded.direction,
                entry_low = excluded.entry_low,
                entry_high = excluded.entry_high,
                stop_loss = excluded.stop_loss,
                confidence_score = excluded.confidence_score,
                risk_reward = excluded.risk_reward,
                holding_horizon_days = excluded.holding_horizon_days,
                regime = excluded.regime,
                reliability_label = excluded.reliability_label,
                rationale_json = excluded.rationale_json,
                warning_flags_json = excluded.warning_flags_json,
                top_factors_json = excluded.top_factors_json,
                profile_version = excluded.profile_version,
                updated_at = excluded.updated_at
            """,
            (
                prediction.prediction_id,
                prediction.ticker,
                prediction.session_date.isoformat(),
                prediction.direction,
                prediction.entry_low,
                prediction.entry_high,
                prediction.stop_loss,
                prediction.confidence_score,
                prediction.risk_reward,
                prediction.holding_horizon_days,
                prediction.regime,
                prediction.reliability_label,
                json_dumps(prediction.rationale),
                json_dumps(prediction.warning_flags),
                json_dumps(prediction.top_factors),
                prediction.profile_version,
                generated_at,
                generated_at,
            ),
        )

    def _upsert_target(self, connection: sqlite3.Connection, prediction_id: str, target: TargetLevel, generated_at: str) -> None:
        connection.execute(
            """
            INSERT INTO targets (
                target_id, prediction_id, kind, price, probability, distance_atr, rationale, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(prediction_id, kind) DO UPDATE SET
                price = excluded.price,
                probability = excluded.probability,
                distance_atr = excluded.distance_atr,
                rationale = excluded.rationale,
                updated_at = excluded.updated_at
            """,
            (
                f"{prediction_id}:{target.kind}",
                prediction_id,
                target.kind,
                target.price,
                target.probability,
                target.distance_atr,
                target.rationale,
                generated_at,
                generated_at,
            ),
        )

    def _upsert_signal_history(self, connection: sqlite3.Connection, history_row: SignalOutcome, generated_at: str) -> None:
        connection.execute(
            """
            INSERT INTO signal_history (
                signal_id, prediction_id, ticker, session_date, direction, regime, outcome_status,
                target_1_hit, target_2_hit, stop_hit, max_adverse_excursion, max_favorable_excursion,
                realized_return_pct, holding_days, target_error, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(prediction_id) DO UPDATE SET
                outcome_status = excluded.outcome_status,
                target_1_hit = excluded.target_1_hit,
                target_2_hit = excluded.target_2_hit,
                stop_hit = excluded.stop_hit,
                max_adverse_excursion = excluded.max_adverse_excursion,
                max_favorable_excursion = excluded.max_favorable_excursion,
                realized_return_pct = excluded.realized_return_pct,
                holding_days = excluded.holding_days,
                target_error = excluded.target_error,
                updated_at = excluded.updated_at
            """,
            (
                history_row.prediction_id,
                history_row.prediction_id,
                history_row.ticker,
                history_row.session_date.isoformat(),
                history_row.direction,
                history_row.regime,
                history_row.outcome_status,
                int(history_row.target_1_hit),
                int(history_row.target_2_hit),
                int(history_row.stop_hit),
                history_row.max_adverse_excursion,
                history_row.max_favorable_excursion,
                history_row.realized_return_pct,
                history_row.holding_days,
                history_row.target_error,
                generated_at,
                generated_at,
            ),
        )

    def get_ui_preferences(self, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM ui_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return {"theme": "system", "density": "comfortable", "default_view": "overview", "favorite_metric": "confidence"}
        payload = dict(row)
        payload.update(json.loads(payload.pop("preferences_json")))
        return payload

    def save_ui_preferences(self, preferences: dict[str, Any], user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
        updated_at = now_iso()
        merged = {
            "theme": preferences.get("theme", "system"),
            "density": preferences.get("density", "comfortable"),
            "default_view": preferences.get("default_view", "overview"),
            "favorite_metric": preferences.get("favorite_metric", "confidence"),
            "show_only_actionable": bool(preferences.get("show_only_actionable", False)),
        }
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO ui_preferences (
                    preference_id, user_id, theme, density, default_view, favorite_metric,
                    preferences_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    theme = excluded.theme,
                    density = excluded.density,
                    default_view = excluded.default_view,
                    favorite_metric = excluded.favorite_metric,
                    preferences_json = excluded.preferences_json,
                    updated_at = excluded.updated_at
                """,
                (
                    f"prefs:{user_id}",
                    user_id,
                    merged["theme"],
                    merged["density"],
                    merged["default_view"],
                    merged["favorite_metric"],
                    json_dumps(merged),
                    updated_at,
                    updated_at,
                ),
            )
            connection.commit()
        return merged

    def build_dashboard_bundle(self, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
        with self.connect() as connection:
            watchlist = self.list_active_tickers(user_id)
            settings = self.get_ui_preferences(user_id)
            latest_run = connection.execute(
                "SELECT completed_at, summary_json FROM backtest_runs ORDER BY completed_at DESC LIMIT 1"
            ).fetchone()
            generated_at = latest_run["completed_at"] if latest_run else now_iso()
            latest_summary = json.loads(latest_run["summary_json"]) if latest_run and latest_run["summary_json"] else {}
            ticker_payloads = {ticker: self.get_ticker_detail(ticker, connection=connection) for ticker in watchlist}
            signals = [payload["latest_prediction"] for payload in ticker_payloads.values() if payload["latest_prediction"]]
            watchlist_rows = [payload["summary"] for payload in ticker_payloads.values() if payload["summary"]]
            history_rows = connection.execute(
                """
                SELECT ticker, session_date, direction, outcome_status, realized_return_pct, holding_days
                FROM signal_history
                ORDER BY session_date DESC
                LIMIT 150
                """
            ).fetchall()
            backtest_rows = connection.execute(
                """
                SELECT run_id, completed_at, summary_json
                FROM backtest_runs
                ORDER BY completed_at DESC
                LIMIT 12
                """
            ).fetchall()

        overview = {
            "tracked_tickers": len(watchlist_rows),
            "long_count": sum(1 for row in signals if row.get("direction") == "long"),
            "short_count": sum(1 for row in signals if row.get("direction") == "short"),
            "neutral_count": sum(1 for row in signals if row.get("direction") == "neutral"),
            "high_confidence_count": sum(1 for row in signals if (row.get("confidence_score") or 0) >= 0.72),
            "avg_confidence": round(sum((row.get("confidence_score") or 0) for row in signals) / len(signals), 4) if signals else 0.0,
            "generated_at": generated_at,
        }
        return {
            "generated_at": generated_at,
            "market_context": latest_summary.get("market_context", {}),
            "overview": overview,
            "watchlist": watchlist_rows,
            "signals": sorted(
                signals,
                key=lambda row: (row.get("direction") == "neutral", -(row.get("confidence_score") or 0), row.get("ticker")),
            ),
            "history": [dict(row) for row in history_rows],
            "tickers": ticker_payloads,
            "settings": settings,
            "backtest_runs": [
                {
                    "run_id": row["run_id"],
                    "completed_at": row["completed_at"],
                    **json.loads(row["summary_json"]),
                }
                for row in backtest_rows
            ],
        }

    def get_ticker_detail(self, ticker: str, *, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
        if connection is None:
            with self.connect() as own_connection:
                return self.get_ticker_detail(ticker, connection=own_connection)

        prediction_row = connection.execute(
            """
            SELECT *
            FROM predictions
            WHERE ticker = ?
            ORDER BY session_date DESC
            LIMIT 1
            """,
            (ticker,),
        ).fetchone()
        profile_row = connection.execute(
            "SELECT * FROM ticker_profiles WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        snapshot_rows = connection.execute(
            """
            SELECT session_date, close, atr, adx, rsi, support, resistance, trend, market_regime, drawdown_63d, relative_strength_1m
            FROM ticker_daily_snapshots
            WHERE ticker = ?
            ORDER BY session_date DESC
            LIMIT 120
            """,
            (ticker,),
        ).fetchall()
        history_rows = connection.execute(
            """
            SELECT session_date, direction, outcome_status, realized_return_pct, holding_days, target_1_hit, target_2_hit, stop_hit
            FROM signal_history
            WHERE ticker = ?
            ORDER BY session_date DESC
            LIMIT 50
            """,
            (ticker,),
        ).fetchall()
        target_rows = []
        if prediction_row:
            target_rows = connection.execute(
                """
                SELECT kind, price, probability, distance_atr, rationale
                FROM targets
                WHERE prediction_id = ?
                ORDER BY CASE kind
                    WHEN 'target_1' THEN 1
                    WHEN 'target_2' THEN 2
                    ELSE 3
                END
                """,
                (prediction_row["prediction_id"],),
            ).fetchall()

        latest_prediction = None
        if prediction_row:
            latest_prediction = dict(prediction_row)
            latest_prediction["rationale"] = json.loads(latest_prediction.pop("rationale_json"))
            latest_prediction["warning_flags"] = json.loads(latest_prediction.pop("warning_flags_json"))
            latest_prediction["top_factors"] = json.loads(latest_prediction.pop("top_factors_json"))
            latest_prediction["targets"] = [dict(row) for row in target_rows]

        summary = None
        if latest_prediction and profile_row and snapshot_rows:
            latest_snapshot = dict(snapshot_rows[0])
            summary = {
                "ticker": ticker,
                "direction": latest_prediction["direction"],
                "confidence_score": latest_prediction["confidence_score"],
                "risk_reward": latest_prediction["risk_reward"],
                "reliability_label": latest_prediction["reliability_label"],
                "regime": latest_prediction["regime"],
                "close": latest_snapshot["close"],
                "trend": latest_snapshot["trend"],
                "relative_strength_1m": latest_snapshot["relative_strength_1m"],
                "target_shrink_factor": profile_row["target_shrink_factor"],
                "sample_size": profile_row["sample_size"],
                "warning_flags": latest_prediction["warning_flags"],
            }

        return {
            "ticker": ticker,
            "summary": summary,
            "latest_prediction": latest_prediction,
            "profile": dict(profile_row) if profile_row else None,
            "snapshots": [dict(row) for row in reversed(snapshot_rows)],
            "signal_history": [dict(row) for row in history_rows],
        }

    def export_table_rows(self, table_name: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(f"SELECT * FROM {table_name}").fetchall()
        return [dict(row) for row in rows]
