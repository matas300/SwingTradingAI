from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from .constants import DEFAULT_TICKERS, DEFAULT_USER_ID, DEFAULT_USER_NAME
from .models import (
    FeatureSnapshot,
    PositionDailySnapshot,
    PositionEvent,
    PositionRecommendation,
    PositionSummary,
    PredictionRecord,
    ProfileSnapshot,
    SignalOutcome,
    TargetLevel,
    TargetSetRecord,
    TickerPipelineResult,
)
from .position_lifecycle import rebuild_position_summary
from .position_policy import recommend_position_action
from .target_engine import adaptive_position_targets, signal_target_set
from .validation import ensure_non_negative_number, ensure_positive_number, normalize_ticker, normalize_ticker_list


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


SYNC_TABLES = (
    "users",
    "watched_tickers",
    "ticker_daily_snapshots",
    "ticker_profiles",
    "signals",
    "signal_versions",
    "signal_history",
    "targets",
    "target_revisions",
    "open_positions",
    "position_events",
    "position_daily_snapshots",
    "position_recommendations",
    "backtest_runs",
    "ui_preferences",
)


class SQLiteRepository:
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
                UNIQUE(user_id, ticker)
            )
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
                ema_fast REAL NOT NULL,
                ema_slow REAL NOT NULL,
                sma50 REAL NOT NULL,
                sma200 REAL,
                support REAL,
                resistance REAL,
                recent_high REAL,
                recent_low REAL,
                volume_ratio REAL NOT NULL,
                volatility_20d REAL NOT NULL,
                drawdown_63d REAL NOT NULL,
                relative_strength_1m REAL NOT NULL,
                relative_strength_3m REAL NOT NULL,
                close_vs_ema21_atr REAL NOT NULL,
                close_to_support_atr REAL,
                close_to_resistance_atr REAL,
                breakout TEXT,
                trend TEXT NOT NULL,
                market_regime TEXT NOT NULL,
                gap_pct REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(ticker, session_date)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS ticker_profiles (
                profile_id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL UNIQUE,
                sample_size INTEGER NOT NULL,
                closed_signal_count INTEGER NOT NULL,
                long_win_rate REAL NOT NULL,
                short_win_rate REAL NOT NULL,
                setup_specific_win_rate REAL NOT NULL,
                volatility_rolling REAL NOT NULL,
                atr_rolling REAL NOT NULL,
                trend_persistence REAL NOT NULL,
                gap_behavior REAL NOT NULL,
                recent_drawdown REAL NOT NULL,
                mean_target_error REAL NOT NULL,
                mean_mae REAL NOT NULL,
                mean_mfe REAL NOT NULL,
                avg_days_to_target REAL,
                avg_days_to_stop REAL,
                average_time_to_target REAL,
                average_time_to_stop REAL,
                target_overshoot_rate REAL NOT NULL,
                target_undershoot_rate REAL NOT NULL,
                confidence_calibration_error REAL NOT NULL,
                regime_distribution_json TEXT NOT NULL,
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
            CREATE TABLE IF NOT EXISTS signals (
                signal_id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                session_date TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
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
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS signal_versions (
                version_id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL,
                version_label TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_low REAL,
                entry_high REAL,
                stop_loss REAL,
                confidence_score REAL NOT NULL,
                risk_reward REAL,
                holding_horizon_days INTEGER NOT NULL,
                regime TEXT NOT NULL,
                rationale_json TEXT NOT NULL,
                warning_flags_json TEXT NOT NULL,
                top_factors_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(signal_id, version_label)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS signal_history (
                id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL UNIQUE,
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
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS targets (
                id TEXT PRIMARY KEY,
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                ticker TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_reference_price REAL,
                average_entry_reference REAL,
                stop_loss REAL,
                target_1 REAL,
                target_2 REAL,
                target_3 REAL,
                probabilistic_target REAL,
                risk_reward REAL,
                confidence_score REAL,
                holding_horizon_estimate INTEGER,
                rationale_json TEXT NOT NULL,
                warning_flags_json TEXT NOT NULL,
                version_label TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(subject_type, subject_id, scope)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS target_revisions (
                revision_id TEXT PRIMARY KEY,
                target_id TEXT NOT NULL,
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                revision_number INTEGER NOT NULL,
                stop_loss REAL,
                target_1 REAL,
                target_2 REAL,
                target_3 REAL,
                probabilistic_target REAL,
                risk_reward REAL,
                confidence_score REAL,
                holding_horizon_estimate INTEGER,
                rationale_json TEXT NOT NULL,
                warning_flags_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS open_positions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                signal_id_origin TEXT NOT NULL,
                side TEXT NOT NULL,
                status TEXT NOT NULL,
                initial_entry_price REAL NOT NULL,
                average_entry_price REAL NOT NULL,
                initial_quantity REAL NOT NULL,
                current_quantity REAL NOT NULL,
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                last_recommendation TEXT,
                last_recommendation_confidence REAL,
                last_recommendation_reason TEXT,
                original_stop REAL,
                current_stop REAL,
                current_price REAL,
                realized_pnl REAL NOT NULL DEFAULT 0,
                unrealized_pnl REAL NOT NULL DEFAULT 0,
                total_pnl REAL NOT NULL DEFAULT 0,
                gross_exposure REAL NOT NULL DEFAULT 0,
                holding_days INTEGER NOT NULL DEFAULT 0,
                max_favorable_excursion REAL NOT NULL DEFAULT 0,
                max_adverse_excursion REAL NOT NULL DEFAULT 0,
                distance_to_stop_pct REAL,
                distance_to_target_1_pct REAL,
                distance_to_target_2_pct REAL,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS position_events (
                id TEXT PRIMARY KEY,
                position_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                side TEXT NOT NULL,
                event_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL,
                fees REAL NOT NULL DEFAULT 0,
                executed_at TEXT NOT NULL,
                source TEXT NOT NULL,
                linked_signal_id TEXT,
                metadata_json TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS position_daily_snapshots (
                id TEXT PRIMARY KEY,
                position_id TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                close_price REAL NOT NULL,
                current_quantity REAL NOT NULL,
                average_entry_price REAL NOT NULL,
                market_value REAL NOT NULL,
                unrealized_pnl REAL NOT NULL,
                realized_pnl_to_date REAL NOT NULL,
                total_pnl REAL NOT NULL,
                distance_to_stop_pct REAL,
                distance_to_target_1_pct REAL,
                distance_to_target_2_pct REAL,
                regime TEXT NOT NULL,
                action_recommendation TEXT NOT NULL,
                recommendation_confidence REAL NOT NULL,
                recommendation_reason TEXT NOT NULL,
                max_favorable_excursion REAL NOT NULL,
                max_adverse_excursion REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(position_id, snapshot_date)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS position_recommendations (
                id TEXT PRIMARY KEY,
                position_id TEXT NOT NULL,
                effective_at TEXT NOT NULL,
                action TEXT NOT NULL,
                confidence REAL NOT NULL,
                suggested_add_qty REAL,
                suggested_reduce_qty REAL,
                suggested_stop REAL,
                suggested_target_1 REAL,
                suggested_target_2 REAL,
                rationale TEXT NOT NULL,
                warning_flags_json TEXT NOT NULL,
                suggested_zone_low REAL,
                suggested_zone_high REAL,
                created_at TEXT NOT NULL,
                UNIQUE(position_id, effective_at)
            )
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
                show_only_actionable INTEGER NOT NULL DEFAULT 0,
                risk_budget_pct REAL NOT NULL DEFAULT 0.01,
                max_add_fraction REAL NOT NULL DEFAULT 0.25,
                preferences_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        ]
        with self.connect() as connection:
            for statement in statements:
                connection.execute(statement)
            recommendation_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(position_recommendations)").fetchall()
            }
            if "suggested_target_3" not in recommendation_columns:
                connection.execute("ALTER TABLE position_recommendations ADD COLUMN suggested_target_3 REAL")
            if "suggested_size_action" not in recommendation_columns:
                connection.execute(
                    "ALTER TABLE position_recommendations ADD COLUMN suggested_size_action TEXT NOT NULL DEFAULT 'hold'"
                )
            if "updated_at" not in recommendation_columns:
                connection.execute("ALTER TABLE position_recommendations ADD COLUMN updated_at TEXT")
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
                    show_only_actionable, risk_budget_pct, max_add_fraction, preferences_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (
                    f"prefs:{user_id}",
                    user_id,
                    "system",
                    "comfortable",
                    "overview",
                    "confidence",
                    0,
                    0.01,
                    0.25,
                    json_dumps(
                        {
                            "theme": "system",
                            "density": "comfortable",
                            "default_view": "overview",
                            "favorite_metric": "confidence",
                            "show_only_actionable": False,
                            "risk_budget_pct": 0.01,
                            "max_add_fraction": 0.25,
                        }
                    ),
                    created_at,
                    created_at,
                ),
            )
            for ticker in tickers:
                normalized = normalize_ticker(ticker)
                connection.execute(
                    """
                    INSERT INTO watched_tickers (watch_id, user_id, ticker, label, notes, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(user_id, ticker) DO UPDATE SET is_active = 1, updated_at = excluded.updated_at
                    """,
                    (f"{user_id}:{normalized}", user_id, normalized, None, None, created_at, created_at),
                )
            connection.commit()

    def replace_watchlist(self, tickers: list[str], user_id: str = DEFAULT_USER_ID) -> None:
        updated_at = now_iso()
        normalized = normalize_ticker_list(tickers)
        with self.connect() as connection:
            connection.execute("UPDATE watched_tickers SET is_active = 0, updated_at = ? WHERE user_id = ?", (updated_at, user_id))
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

    def _fetch_string_list(self, query: str, parameters: tuple = ()) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [str(row[0]) for row in rows]

    def list_active_tickers(self, user_id: str = DEFAULT_USER_ID) -> list[str]:
        return self._fetch_string_list(
            "SELECT ticker FROM watched_tickers WHERE user_id = ? AND is_active = 1 ORDER BY ticker",
            (user_id,)
        )

    def list_open_position_tickers(self, user_id: str = DEFAULT_USER_ID) -> list[str]:
        return self._fetch_string_list(
            "SELECT DISTINCT ticker FROM open_positions WHERE user_id = ? AND status = 'open' ORDER BY ticker",
            (user_id,)
        )

    def get_ui_preferences(self, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM ui_preferences WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return {
                "theme": "system",
                "density": "comfortable",
                "default_view": "overview",
                "favorite_metric": "confidence",
                "show_only_actionable": False,
                "risk_budget_pct": 0.01,
                "max_add_fraction": 0.25,
            }
        payload = dict(row)
        payload.update(json.loads(payload.pop("preferences_json")))
        payload["show_only_actionable"] = bool(payload.get("show_only_actionable"))
        return payload

    def save_ui_preferences(self, preferences: dict[str, Any], user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
        updated_at = now_iso()
        merged = {
            "theme": preferences.get("theme", "system"),
            "density": preferences.get("density", "comfortable"),
            "default_view": preferences.get("default_view", "overview"),
            "favorite_metric": preferences.get("favorite_metric", "confidence"),
            "show_only_actionable": bool(preferences.get("show_only_actionable", False)),
            "risk_budget_pct": float(preferences.get("risk_budget_pct", 0.01)),
            "max_add_fraction": float(preferences.get("max_add_fraction", 0.25)),
        }
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO ui_preferences (
                    preference_id, user_id, theme, density, default_view, favorite_metric,
                    show_only_actionable, risk_budget_pct, max_add_fraction, preferences_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    theme = excluded.theme,
                    density = excluded.density,
                    default_view = excluded.default_view,
                    favorite_metric = excluded.favorite_metric,
                    show_only_actionable = excluded.show_only_actionable,
                    risk_budget_pct = excluded.risk_budget_pct,
                    max_add_fraction = excluded.max_add_fraction,
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
                    int(merged["show_only_actionable"]),
                    merged["risk_budget_pct"],
                    merged["max_add_fraction"],
                    json_dumps(merged),
                    updated_at,
                    updated_at,
                ),
            )
            connection.commit()
        return merged

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
                    configuration_json = excluded.configuration_json,
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
        self._upsert_profile(connection, result.profile, generated_at)
        for snapshot in result.snapshots:
            self._upsert_snapshot(connection, snapshot, generated_at)
        for prediction in result.historical_predictions:
            self._upsert_signal(connection, prediction, generated_at)
            targets = result.historical_targets.get(prediction.signal_id, [])
            self._upsert_target_set(connection, signal_target_set(prediction, targets), generated_at)
        for history_row in result.signal_history:
            self._upsert_signal_history(connection, history_row, generated_at)

    def _upsert_snapshot(self, connection: sqlite3.Connection, snapshot: FeatureSnapshot, generated_at: str) -> None:
        connection.execute(
            """
            INSERT INTO ticker_daily_snapshots (
                snapshot_id, ticker, session_date, open, high, low, close, volume, atr, adx, rsi,
                ema_fast, ema_slow, sma50, sma200, support, resistance, recent_high, recent_low,
                volume_ratio, volatility_20d, drawdown_63d, relative_strength_1m, relative_strength_3m,
                close_vs_ema21_atr, close_to_support_atr, close_to_resistance_atr, breakout, trend,
                market_regime, gap_pct, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, session_date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                atr = excluded.atr,
                adx = excluded.adx,
                rsi = excluded.rsi,
                ema_fast = excluded.ema_fast,
                ema_slow = excluded.ema_slow,
                sma50 = excluded.sma50,
                sma200 = excluded.sma200,
                support = excluded.support,
                resistance = excluded.resistance,
                recent_high = excluded.recent_high,
                recent_low = excluded.recent_low,
                volume_ratio = excluded.volume_ratio,
                volatility_20d = excluded.volatility_20d,
                drawdown_63d = excluded.drawdown_63d,
                relative_strength_1m = excluded.relative_strength_1m,
                relative_strength_3m = excluded.relative_strength_3m,
                close_vs_ema21_atr = excluded.close_vs_ema21_atr,
                close_to_support_atr = excluded.close_to_support_atr,
                close_to_resistance_atr = excluded.close_to_resistance_atr,
                breakout = excluded.breakout,
                trend = excluded.trend,
                market_regime = excluded.market_regime,
                gap_pct = excluded.gap_pct,
                updated_at = excluded.updated_at
            """,
            (
                f"snapshot:{snapshot.ticker}:{snapshot.session_date.isoformat()}",
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
                snapshot.ema_fast,
                snapshot.ema_slow,
                snapshot.sma50,
                snapshot.sma200,
                snapshot.support,
                snapshot.resistance,
                snapshot.recent_high,
                snapshot.recent_low,
                snapshot.volume_ratio,
                snapshot.volatility_20d,
                snapshot.drawdown_63d,
                snapshot.relative_strength_1m,
                snapshot.relative_strength_3m,
                snapshot.close_vs_ema21_atr,
                snapshot.close_to_support_atr,
                snapshot.close_to_resistance_atr,
                snapshot.breakout,
                snapshot.trend,
                snapshot.market_regime,
                snapshot.gap_pct,
                generated_at,
                generated_at,
            ),
        )

    def _upsert_profile(self, connection: sqlite3.Connection, profile: ProfileSnapshot, generated_at: str) -> None:
        connection.execute(
            """
            INSERT INTO ticker_profiles (
                profile_id, ticker, sample_size, closed_signal_count, long_win_rate, short_win_rate,
                setup_specific_win_rate, volatility_rolling, atr_rolling, trend_persistence, gap_behavior,
                recent_drawdown, mean_target_error, mean_mae, mean_mfe, avg_days_to_target, avg_days_to_stop,
                average_time_to_target, average_time_to_stop, target_overshoot_rate, target_undershoot_rate,
                confidence_calibration_error, regime_distribution_json, long_effectiveness, short_effectiveness,
                dominant_regime, confidence_floor, target_aggression, target_shrink_factor, reliability_score,
                insufficient_data, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                sample_size = excluded.sample_size,
                closed_signal_count = excluded.closed_signal_count,
                long_win_rate = excluded.long_win_rate,
                short_win_rate = excluded.short_win_rate,
                setup_specific_win_rate = excluded.setup_specific_win_rate,
                volatility_rolling = excluded.volatility_rolling,
                atr_rolling = excluded.atr_rolling,
                trend_persistence = excluded.trend_persistence,
                gap_behavior = excluded.gap_behavior,
                recent_drawdown = excluded.recent_drawdown,
                mean_target_error = excluded.mean_target_error,
                mean_mae = excluded.mean_mae,
                mean_mfe = excluded.mean_mfe,
                avg_days_to_target = excluded.avg_days_to_target,
                avg_days_to_stop = excluded.avg_days_to_stop,
                average_time_to_target = excluded.average_time_to_target,
                average_time_to_stop = excluded.average_time_to_stop,
                target_overshoot_rate = excluded.target_overshoot_rate,
                target_undershoot_rate = excluded.target_undershoot_rate,
                confidence_calibration_error = excluded.confidence_calibration_error,
                regime_distribution_json = excluded.regime_distribution_json,
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
                profile.setup_specific_win_rate,
                profile.volatility_rolling,
                profile.atr_rolling,
                profile.trend_persistence,
                profile.gap_behavior,
                profile.recent_drawdown,
                profile.mean_target_error,
                profile.mean_mae,
                profile.mean_mfe,
                profile.avg_days_to_target,
                profile.avg_days_to_stop,
                profile.average_time_to_target,
                profile.average_time_to_stop,
                profile.target_overshoot_rate,
                profile.target_undershoot_rate,
                profile.confidence_calibration_error,
                json_dumps(profile.regime_distribution),
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

    def _upsert_signal(self, connection: sqlite3.Connection, prediction: PredictionRecord, generated_at: str) -> None:
        connection.execute(
            """
            INSERT INTO signals (
                signal_id, ticker, session_date, strategy_id, strategy_name, direction, entry_low, entry_high,
                stop_loss, confidence_score, risk_reward, holding_horizon_days, regime, reliability_label,
                rationale_json, warning_flags_json, top_factors_json, profile_version, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(signal_id) DO UPDATE SET
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
                prediction.signal_id,
                prediction.ticker,
                prediction.session_date.isoformat(),
                prediction.strategy_id,
                prediction.strategy_name,
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
        connection.execute(
            """
            INSERT INTO signal_versions (
                version_id, signal_id, version_label, direction, entry_low, entry_high, stop_loss,
                confidence_score, risk_reward, holding_horizon_days, regime, rationale_json,
                warning_flags_json, top_factors_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(signal_id, version_label) DO UPDATE SET
                direction = excluded.direction,
                entry_low = excluded.entry_low,
                entry_high = excluded.entry_high,
                stop_loss = excluded.stop_loss,
                confidence_score = excluded.confidence_score,
                risk_reward = excluded.risk_reward,
                holding_horizon_days = excluded.holding_horizon_days,
                regime = excluded.regime,
                rationale_json = excluded.rationale_json,
                warning_flags_json = excluded.warning_flags_json,
                top_factors_json = excluded.top_factors_json,
                created_at = excluded.created_at
            """,
            (
                f"version:{prediction.signal_id}:{prediction.profile_version}",
                prediction.signal_id,
                prediction.profile_version,
                prediction.direction,
                prediction.entry_low,
                prediction.entry_high,
                prediction.stop_loss,
                prediction.confidence_score,
                prediction.risk_reward,
                prediction.holding_horizon_days,
                prediction.regime,
                json_dumps(prediction.rationale),
                json_dumps(prediction.warning_flags),
                json_dumps(prediction.top_factors),
                generated_at,
            ),
        )

    def _upsert_signal_history(self, connection: sqlite3.Connection, history_row: SignalOutcome, generated_at: str) -> None:
        connection.execute(
            """
            INSERT INTO signal_history (
                id, signal_id, ticker, session_date, direction, regime, outcome_status, target_1_hit, target_2_hit,
                stop_hit, max_adverse_excursion, max_favorable_excursion, realized_return_pct, holding_days,
                target_error, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(signal_id) DO UPDATE SET
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
                f"history:{history_row.signal_id}",
                history_row.signal_id,
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

    def _upsert_target_set(self, connection: sqlite3.Connection, target_set: TargetSetRecord, generated_at: str) -> None:
        connection.execute(
            """
            INSERT INTO targets (
                id, subject_type, subject_id, scope, ticker, side, entry_reference_price,
                average_entry_reference, stop_loss, target_1, target_2, target_3, probabilistic_target,
                risk_reward, confidence_score, holding_horizon_estimate, rationale_json, warning_flags_json,
                version_label, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(subject_type, subject_id, scope) DO UPDATE SET
                entry_reference_price = excluded.entry_reference_price,
                average_entry_reference = excluded.average_entry_reference,
                stop_loss = excluded.stop_loss,
                target_1 = excluded.target_1,
                target_2 = excluded.target_2,
                target_3 = excluded.target_3,
                probabilistic_target = excluded.probabilistic_target,
                risk_reward = excluded.risk_reward,
                confidence_score = excluded.confidence_score,
                holding_horizon_estimate = excluded.holding_horizon_estimate,
                rationale_json = excluded.rationale_json,
                warning_flags_json = excluded.warning_flags_json,
                version_label = excluded.version_label,
                updated_at = excluded.updated_at
            """,
            (
                target_set.target_id,
                target_set.owner_type,
                target_set.owner_id,
                target_set.scope,
                target_set.ticker,
                target_set.side,
                target_set.entry_reference_price,
                target_set.average_entry_reference,
                target_set.stop_loss,
                target_set.target_1,
                target_set.target_2,
                target_set.target_3,
                target_set.probabilistic_target,
                target_set.risk_reward,
                target_set.confidence_score,
                target_set.holding_horizon_estimate,
                json_dumps(target_set.rationale),
                json_dumps(target_set.warning_flags),
                target_set.version_label,
                generated_at,
                generated_at,
            ),
        )
        current_revision = connection.execute(
            "SELECT COALESCE(MAX(revision_number), 0) AS revision_number FROM target_revisions WHERE target_id = ?",
            (target_set.target_id,),
        ).fetchone()
        revision_number = int(current_revision["revision_number"]) + 1 if current_revision else 1
        connection.execute(
            """
            INSERT INTO target_revisions (
                revision_id, target_id, subject_type, subject_id, scope, revision_number, stop_loss, target_1,
                target_2, target_3, probabilistic_target, risk_reward, confidence_score, holding_horizon_estimate,
                rationale_json, warning_flags_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{target_set.target_id}:rev:{revision_number}",
                target_set.target_id,
                target_set.owner_type,
                target_set.owner_id,
                target_set.scope,
                revision_number,
                target_set.stop_loss,
                target_set.target_1,
                target_set.target_2,
                target_set.target_3,
                target_set.probabilistic_target,
                target_set.risk_reward,
                target_set.confidence_score,
                target_set.holding_horizon_estimate,
                json_dumps(target_set.rationale),
                json_dumps(target_set.warning_flags),
                generated_at,
            ),
        )

    def _row_to_profile(self, row: sqlite3.Row) -> ProfileSnapshot:
        return ProfileSnapshot(
            ticker=row["ticker"],
            sample_size=int(row["sample_size"]),
            closed_signal_count=int(row["closed_signal_count"]),
            long_win_rate=float(row["long_win_rate"]),
            short_win_rate=float(row["short_win_rate"]),
            volatility_rolling=float(row["volatility_rolling"]),
            atr_rolling=float(row["atr_rolling"]),
            trend_persistence=float(row["trend_persistence"]),
            gap_behavior=float(row["gap_behavior"]),
            recent_drawdown=float(row["recent_drawdown"]),
            mean_target_error=float(row["mean_target_error"]),
            mean_mae=float(row["mean_mae"]),
            mean_mfe=float(row["mean_mfe"]),
            avg_days_to_target=float(row["avg_days_to_target"]) if row["avg_days_to_target"] is not None else None,
            avg_days_to_stop=float(row["avg_days_to_stop"]) if row["avg_days_to_stop"] is not None else None,
            long_effectiveness=float(row["long_effectiveness"]),
            short_effectiveness=float(row["short_effectiveness"]),
            dominant_regime=str(row["dominant_regime"]),
            confidence_floor=float(row["confidence_floor"]),
            target_aggression=float(row["target_aggression"]),
            target_shrink_factor=float(row["target_shrink_factor"]),
            reliability_score=float(row["reliability_score"]),
            insufficient_data=bool(row["insufficient_data"]),
            setup_win_rate=float(row["setup_specific_win_rate"]),
            target_overshoot_rate=float(row["target_overshoot_rate"]),
            target_undershoot_rate=float(row["target_undershoot_rate"]),
            confidence_calibration_error=float(row["confidence_calibration_error"]),
            regime_distribution=json.loads(row["regime_distribution_json"]),
        )

    def _row_to_prediction(self, row: sqlite3.Row) -> PredictionRecord:
        return PredictionRecord(
            prediction_id=str(row["signal_id"]),
            ticker=str(row["ticker"]),
            session_date=parse_date(str(row["session_date"])) or date.today(),
            direction=str(row["direction"]),
            entry_low=float(row["entry_low"]) if row["entry_low"] is not None else None,
            entry_high=float(row["entry_high"]) if row["entry_high"] is not None else None,
            stop_loss=float(row["stop_loss"]) if row["stop_loss"] is not None else None,
            confidence_score=float(row["confidence_score"]),
            risk_reward=float(row["risk_reward"]) if row["risk_reward"] is not None else None,
            holding_horizon_days=int(row["holding_horizon_days"]),
            regime=str(row["regime"]),
            reliability_label=str(row["reliability_label"]),
            rationale=json.loads(row["rationale_json"]),
            warning_flags=json.loads(row["warning_flags_json"]),
            top_factors=json.loads(row["top_factors_json"]),
            profile_version=str(row["profile_version"]),
            strategy_id=str(row["strategy_id"]),
            signal_id=str(row["signal_id"]),
            generated_at=str(row["updated_at"]),
            setup_name=str(row["strategy_name"]),
            setup_quality=str(json.loads(row["rationale_json"]).get("setup_quality", "balanced")),
        )

    def _row_to_target_set(self, row: sqlite3.Row) -> TargetSetRecord:
        return TargetSetRecord(
            target_id=str(row["id"]),
            owner_type=str(row["subject_type"]),
            owner_id=str(row["subject_id"]),
            scope=str(row["scope"]),
            side=str(row["side"]),
            reference_entry_price=float(row["entry_reference_price"]) if row["entry_reference_price"] is not None else None,
            average_entry_price=float(row["average_entry_reference"]) if row["average_entry_reference"] is not None else None,
            stop_loss=float(row["stop_loss"]) if row["stop_loss"] is not None else None,
            target_1=float(row["target_1"]) if row["target_1"] is not None else None,
            target_2=float(row["target_2"]) if row["target_2"] is not None else None,
            optional_target_3=float(row["target_3"]) if row["target_3"] is not None else None,
            probabilistic_target=float(row["probabilistic_target"]) if row["probabilistic_target"] is not None else None,
            risk_reward=float(row["risk_reward"]) if row["risk_reward"] is not None else None,
            confidence_score=float(row["confidence_score"]) if row["confidence_score"] is not None else None,
            holding_horizon_days=int(row["holding_horizon_estimate"]) if row["holding_horizon_estimate"] is not None else 0,
            rationale=json.loads(row["rationale_json"]),
            warning_flags=json.loads(row["warning_flags_json"]),
            generated_at=str(row["updated_at"]),
            version_tag=str(row["version_label"]),
            ticker_symbol=str(row["ticker"]),
        )

    def _target_set_to_levels(self, target_set: TargetSetRecord, scope: str) -> list[TargetLevel]:
        reference = target_set.average_entry_reference or target_set.entry_reference_price
        levels: list[TargetLevel] = []
        for kind, price in (
            ("target_1", target_set.target_1),
            ("target_2", target_set.target_2),
            ("probabilistic_target", target_set.probabilistic_target),
        ):
            if price is None:
                continue
            distance = 0.0
            if reference is not None and reference != 0:
                distance = abs(price - reference) / max(abs(reference), 0.0001)
            levels.append(
                TargetLevel(
                    kind=kind,
                    price=float(price),
                    probability=target_set.confidence_score,
                    distance_atr=distance,
                    rationale=str(target_set.rationale.get("summary", target_set.rationale)),
                    scope=scope,
                    reference_price=reference,
                )
            )
        return levels

    def _row_to_position_event(self, row: sqlite3.Row) -> PositionEvent:
        return PositionEvent(
            event_id=str(row["id"]),
            position_id=str(row["position_id"]),
            user_id="",
            ticker=str(row["ticker"]),
            side=str(row["side"]),
            event_type=str(row["event_type"]),
            quantity=float(row["quantity"]),
            price=float(row["price"]) if row["price"] is not None else None,
            fees=float(row["fees"]),
            executed_at=parse_timestamp(str(row["executed_at"])) or datetime.utcnow(),
            source=str(row["source"]),
            linked_signal_id=str(row["linked_signal_id"]) if row["linked_signal_id"] else None,
            metadata=json.loads(row["metadata_json"]),
            notes=str(row["notes"] or ""),
        )

    def _row_to_position_summary(self, row: sqlite3.Row, original_targets: list[TargetLevel], adaptive_targets: list[TargetLevel]) -> PositionSummary:
        return PositionSummary(
            position_id=str(row["id"]),
            user_id=str(row["user_id"]),
            ticker=str(row["ticker"]),
            strategy_id=str(row["strategy_id"]),
            signal_id_origin=str(row["signal_id_origin"]),
            side=str(row["side"]),
            status=str(row["status"]),
            initial_entry_price=float(row["initial_entry_price"]),
            average_entry_price=float(row["average_entry_price"]),
            initial_quantity=float(row["initial_quantity"]),
            current_quantity=float(row["current_quantity"]),
            opened_at=parse_timestamp(str(row["opened_at"])) or datetime.utcnow(),
            closed_at=parse_timestamp(str(row["closed_at"])) if row["closed_at"] else None,
            current_stop=float(row["current_stop"]) if row["current_stop"] is not None else None,
            original_stop=float(row["original_stop"]) if row["original_stop"] is not None else None,
            targets_from_original_signal=original_targets,
            current_adaptive_targets=adaptive_targets,
            realized_pnl=float(row["realized_pnl"]),
            unrealized_pnl=float(row["unrealized_pnl"]),
            total_pnl=float(row["total_pnl"]),
            gross_exposure=float(row["gross_exposure"]),
            holding_days=int(row["holding_days"]),
            max_favorable_excursion=float(row["max_favorable_excursion"]),
            max_adverse_excursion=float(row["max_adverse_excursion"]),
            distance_to_stop_pct=float(row["distance_to_stop_pct"]) if row["distance_to_stop_pct"] is not None else None,
            distance_to_target_1_pct=float(row["distance_to_target_1_pct"]) if row["distance_to_target_1_pct"] is not None else None,
            distance_to_target_2_pct=float(row["distance_to_target_2_pct"]) if row["distance_to_target_2_pct"] is not None else None,
            mark_price=float(row["current_price"]) if row["current_price"] is not None else None,
            last_recommendation=str(row["last_recommendation"]) if row["last_recommendation"] else None,
            last_recommendation_confidence=float(row["last_recommendation_confidence"]) if row["last_recommendation_confidence"] is not None else None,
            last_recommendation_reason=str(row["last_recommendation_reason"]) if row["last_recommendation_reason"] else None,
            notes=str(row["notes"] or ""),
        )

    def get_latest_signal(self, ticker: str, *, connection: sqlite3.Connection | None = None) -> PredictionRecord | None:
        ticker = normalize_ticker(ticker)
        if connection is None:
            with self.connect() as own_connection:
                return self.get_latest_signal(ticker, connection=own_connection)
        row = connection.execute(
            "SELECT * FROM signals WHERE ticker = ? ORDER BY session_date DESC, updated_at DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        return self._row_to_prediction(row) if row else None

    def get_signal_by_id(self, signal_id: str, *, connection: sqlite3.Connection | None = None) -> PredictionRecord | None:
        if connection is None:
            with self.connect() as own_connection:
                return self.get_signal_by_id(signal_id, connection=own_connection)
        row = connection.execute("SELECT * FROM signals WHERE signal_id = ?", (signal_id,)).fetchone()
        return self._row_to_prediction(row) if row else None

    def get_target_set(self, subject_type: str, subject_id: str, scope: str, *, connection: sqlite3.Connection | None = None) -> TargetSetRecord | None:
        if connection is None:
            with self.connect() as own_connection:
                return self.get_target_set(subject_type, subject_id, scope, connection=own_connection)
        row = connection.execute(
            "SELECT * FROM targets WHERE subject_type = ? AND subject_id = ? AND scope = ?",
            (subject_type, subject_id, scope),
        ).fetchone()
        return self._row_to_target_set(row) if row else None

    def _latest_close(self, ticker: str, connection: sqlite3.Connection) -> float | None:
        row = connection.execute(
            "SELECT close FROM ticker_daily_snapshots WHERE ticker = ? ORDER BY session_date DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        return float(row["close"]) if row and row["close"] is not None else None

    def _price_history_since(self, ticker: str, start_date: date, connection: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = connection.execute(
            "SELECT session_date, open, high, low, close FROM ticker_daily_snapshots WHERE ticker = ? AND session_date >= ? ORDER BY session_date",
            (ticker, start_date.isoformat()),
        ).fetchall()
        return [dict(row) for row in rows]

    def _load_position_events(self, position_id: str, connection: sqlite3.Connection) -> list[PositionEvent]:
        rows = connection.execute("SELECT * FROM position_events WHERE position_id = ? ORDER BY executed_at, id", (position_id,)).fetchall()
        return [self._row_to_position_event(row) for row in rows]

    def _upsert_position_row(self, connection: sqlite3.Connection, position: PositionSummary, strategy_name: str, generated_at: str) -> None:
        connection.execute(
            """
            INSERT INTO open_positions (
                id, user_id, ticker, strategy_id, strategy_name, signal_id_origin, side, status,
                initial_entry_price, average_entry_price, initial_quantity, current_quantity, opened_at, closed_at,
                last_recommendation, last_recommendation_confidence, last_recommendation_reason, original_stop,
                current_stop, current_price, realized_pnl, unrealized_pnl, total_pnl, gross_exposure, holding_days,
                max_favorable_excursion, max_adverse_excursion, distance_to_stop_pct, distance_to_target_1_pct,
                distance_to_target_2_pct, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                average_entry_price = excluded.average_entry_price,
                current_quantity = excluded.current_quantity,
                closed_at = excluded.closed_at,
                last_recommendation = excluded.last_recommendation,
                last_recommendation_confidence = excluded.last_recommendation_confidence,
                last_recommendation_reason = excluded.last_recommendation_reason,
                original_stop = excluded.original_stop,
                current_stop = excluded.current_stop,
                current_price = excluded.current_price,
                realized_pnl = excluded.realized_pnl,
                unrealized_pnl = excluded.unrealized_pnl,
                total_pnl = excluded.total_pnl,
                gross_exposure = excluded.gross_exposure,
                holding_days = excluded.holding_days,
                max_favorable_excursion = excluded.max_favorable_excursion,
                max_adverse_excursion = excluded.max_adverse_excursion,
                distance_to_stop_pct = excluded.distance_to_stop_pct,
                distance_to_target_1_pct = excluded.distance_to_target_1_pct,
                distance_to_target_2_pct = excluded.distance_to_target_2_pct,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                position.position_id,
                position.user_id,
                position.ticker,
                position.strategy_id,
                strategy_name,
                position.signal_id_origin,
                position.side,
                position.status,
                position.initial_entry_price,
                position.average_entry_price,
                position.initial_quantity,
                position.current_quantity,
                position.opened_at.isoformat(),
                position.closed_at.isoformat() if position.closed_at else None,
                position.last_recommendation,
                position.last_recommendation_confidence,
                position.last_recommendation_reason,
                position.original_stop,
                position.current_stop,
                position.mark_price,
                position.realized_pnl,
                position.unrealized_pnl,
                position.total_pnl,
                position.gross_exposure,
                position.holding_days,
                position.max_favorable_excursion,
                position.max_adverse_excursion,
                position.distance_to_stop_pct,
                position.distance_to_target_1_pct,
                position.distance_to_target_2_pct,
                position.notes,
                generated_at,
                generated_at,
            ),
        )

    def create_position_from_signal(
        self,
        *,
        signal_id: str,
        quantity: float,
        execution_price: float,
        executed_at: str,
        notes: str = "",
        fees: float = 0.0,
        user_id: str = DEFAULT_USER_ID,
    ) -> dict[str, Any]:
        ensure_positive_number(quantity, "quantity")
        ensure_positive_number(execution_price, "execution_price")
        ensure_non_negative_number(fees, "fees")
        opened_at = parse_timestamp(executed_at) or datetime.utcnow()
        created_at = now_iso()
        with self.connect() as connection:
            signal = self.get_signal_by_id(signal_id, connection=connection)
            if signal is None:
                raise ValueError(f"Signal not found: {signal_id}")
            if signal.direction not in {"long", "short"}:
                raise ValueError("Only long or short signals can open a real position.")
            original_signal_targets = self.get_target_set("signal", signal.signal_id, "signal_original", connection=connection)
            if original_signal_targets is None:
                raise ValueError("Original targets are missing for the selected signal.")
            position_id = f"position:{uuid4().hex[:12]}"
            event = PositionEvent(
                event_id=f"event:{uuid4().hex[:12]}",
                position_id=position_id,
                user_id=user_id,
                ticker=signal.ticker,
                side=signal.direction if signal.direction in {"long", "short"} else "long",
                event_type="OPEN",
                quantity=float(quantity),
                price=float(execution_price),
                fees=float(fees),
                executed_at=opened_at,
                source="user",
                linked_signal_id=signal.signal_id,
                metadata={"opened_from_signal": True},
                notes=notes,
            )
            connection.execute(
                """
                INSERT INTO position_events (
                    id, position_id, ticker, side, event_type, quantity, price, fees, executed_at, source,
                    linked_signal_id, metadata_json, notes, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.position_id,
                    event.ticker,
                    event.side,
                    event.event_type,
                    event.quantity,
                    event.price,
                    event.fees,
                    event.executed_at.isoformat(),
                    event.source,
                    event.linked_signal_id,
                    json_dumps(event.metadata),
                    event.notes,
                    created_at,
                ),
            )
            original_targets = TargetSetRecord(
                target_id=f"targets:position:{position_id}:original",
                owner_type="position",
                owner_id=position_id,
                scope="position_original",
                side=event.side,
                reference_entry_price=original_signal_targets.reference_entry_price,
                average_entry_price=execution_price,
                stop_loss=original_signal_targets.stop_loss,
                target_1=original_signal_targets.target_1,
                target_2=original_signal_targets.target_2,
                optional_target_3=original_signal_targets.target_3,
                probabilistic_target=original_signal_targets.probabilistic_target,
                risk_reward=original_signal_targets.risk_reward,
                confidence_score=original_signal_targets.confidence_score,
                holding_horizon_days=original_signal_targets.holding_horizon_estimate,
                rationale=original_signal_targets.rationale,
                warning_flags=original_signal_targets.warning_flags,
                generated_at=created_at,
                version_tag="position-open",
                ticker_symbol=signal.ticker,
            )
            self._upsert_target_set(connection, original_targets, created_at)
            adaptive_targets = TargetSetRecord(
                target_id=f"targets:position:{position_id}:adaptive",
                owner_type="position",
                owner_id=position_id,
                scope="position_adaptive",
                side=event.side,
                reference_entry_price=execution_price,
                average_entry_price=execution_price,
                stop_loss=original_signal_targets.stop_loss,
                target_1=original_signal_targets.target_1,
                target_2=original_signal_targets.target_2,
                optional_target_3=original_signal_targets.target_3,
                probabilistic_target=original_signal_targets.probabilistic_target,
                risk_reward=original_signal_targets.risk_reward,
                confidence_score=original_signal_targets.confidence_score,
                holding_horizon_days=original_signal_targets.holding_horizon_estimate,
                rationale={"summary": "Adaptive targets inherit the original signal until the next daily refresh."},
                warning_flags=original_signal_targets.warning_flags,
                generated_at=created_at,
                version_tag="position-open",
                ticker_symbol=signal.ticker,
            )
            self._upsert_target_set(connection, adaptive_targets, created_at)
            current_price = self._latest_close(signal.ticker, connection) or execution_price
            summary = rebuild_position_summary(
                position_id=position_id,
                user_id=user_id,
                ticker=signal.ticker,
                strategy_id=signal.strategy_id,
                signal_id_origin=signal.signal_id,
                side=event.side,
                opened_at=opened_at,
                events=[event],
                original_targets=self._target_set_to_levels(original_targets, "original"),
                adaptive_targets=self._target_set_to_levels(adaptive_targets, "adaptive"),
                original_stop=original_targets.stop_loss,
                current_stop=adaptive_targets.stop_loss,
                mark_price=current_price,
                as_of=opened_at,
                price_history=self._price_history_since(signal.ticker, opened_at.date(), connection),
                last_recommendation="maintain",
                last_recommendation_confidence=signal.confidence_score,
                last_recommendation_reason="Position opened from the signal. The next daily refresh will re-evaluate it.",
                base_notes=notes,
            )
            self._upsert_position_row(connection, summary, signal.strategy_name, created_at)
            refreshed_row = connection.execute("SELECT * FROM open_positions WHERE id = ?", (position_id,)).fetchone()
            if refreshed_row is not None:
                self._refresh_position_row(
                    connection,
                    refreshed_row,
                    generated_at=created_at,
                    signal=signal,
                )
            connection.commit()
            return self.get_position_detail(position_id, connection=connection)

    def _refresh_position_row(
        self,
        connection: sqlite3.Connection,
        position_row: sqlite3.Row,
        *,
        generated_at: str,
        signal: PredictionRecord | None = None,
        profile: ProfileSnapshot | None = None,
        market_snapshot: FeatureSnapshot | None = None,
    ) -> PositionSummary:
        position_id = str(position_row["id"])
        ticker = str(position_row["ticker"])
        original_target_set = self.get_target_set("position", position_id, "position_original", connection=connection)
        adaptive_target_set = self.get_target_set("position", position_id, "position_adaptive", connection=connection)
        opened_at = parse_timestamp(str(position_row["opened_at"])) or datetime.utcnow()
        events = self._load_position_events(position_id, connection)
        original_levels = self._target_set_to_levels(original_target_set, "original") if original_target_set else []
        adaptive_levels = (
            self._target_set_to_levels(adaptive_target_set, "adaptive")
            if adaptive_target_set
            else original_levels
        )
        if signal is None:
            signal = self.get_signal_by_id(str(position_row["signal_id_origin"]), connection=connection)
            if signal is None:
                signal = self.get_latest_signal(ticker, connection=connection)
        if profile is None:
            profile_row = connection.execute("SELECT * FROM ticker_profiles WHERE ticker = ?", (ticker,)).fetchone()
            profile = self._row_to_profile(profile_row) if profile_row else None
        if market_snapshot is None:
            latest_snapshot_row = connection.execute(
                "SELECT * FROM ticker_daily_snapshots WHERE ticker = ? ORDER BY session_date DESC LIMIT 1",
                (ticker,),
            ).fetchone()
            market_snapshot = self._row_to_feature(latest_snapshot_row) if latest_snapshot_row else None
        mark_price = (
            market_snapshot.close
            if market_snapshot is not None
            else self._latest_close(ticker, connection)
            or float(position_row["current_price"] or position_row["average_entry_price"])
        )
        price_history = self._price_history_since(ticker, opened_at.date(), connection)
        summary = rebuild_position_summary(
            position_id=position_id,
            user_id=str(position_row["user_id"]),
            ticker=ticker,
            strategy_id=str(position_row["strategy_id"]),
            signal_id_origin=str(position_row["signal_id_origin"]),
            side=str(position_row["side"]),
            opened_at=opened_at,
            events=events,
            original_targets=original_levels,
            adaptive_targets=adaptive_levels,
            original_stop=original_target_set.stop_loss if original_target_set else None,
            current_stop=adaptive_target_set.stop_loss if adaptive_target_set else None,
            mark_price=mark_price,
            as_of=parse_timestamp(generated_at) or datetime.utcnow(),
            price_history=price_history,
            last_recommendation=str(position_row["last_recommendation"] or "maintain"),
            last_recommendation_confidence=(
                float(position_row["last_recommendation_confidence"])
                if position_row["last_recommendation_confidence"] is not None
                else None
            ),
            last_recommendation_reason=str(position_row["last_recommendation_reason"] or ""),
            base_notes=str(position_row["notes"] or ""),
        )

        if original_target_set and signal and profile and market_snapshot:
            adaptive_target_set = adaptive_position_targets(
                position=summary,
                signal=signal,
                profile=profile,
                market_snapshot=market_snapshot,
                original_targets=original_target_set,
            )
            self._upsert_target_set(connection, adaptive_target_set, generated_at)
            summary = rebuild_position_summary(
                position_id=summary.position_id,
                user_id=summary.user_id,
                ticker=summary.ticker,
                strategy_id=summary.strategy_id,
                signal_id_origin=summary.signal_id_origin,
                side=summary.side,
                opened_at=summary.opened_at,
                events=events,
                original_targets=original_levels,
                adaptive_targets=self._target_set_to_levels(adaptive_target_set, "adaptive"),
                original_stop=original_target_set.stop_loss,
                current_stop=adaptive_target_set.stop_loss,
                mark_price=mark_price,
                as_of=parse_timestamp(generated_at) or datetime.utcnow(),
                price_history=price_history,
                last_recommendation=summary.last_recommendation,
                last_recommendation_confidence=summary.last_recommendation_confidence,
                last_recommendation_reason=summary.last_recommendation_reason,
                base_notes=summary.notes,
            )
            recommendation = recommend_position_action(
                position=summary,
                signal=signal,
                profile=profile,
                market_snapshot=market_snapshot,
                original_targets=original_target_set,
                adaptive_targets=adaptive_target_set,
                effective_at=generated_at,
            )
        else:
            recommendation = PositionRecommendation(
                recommendation_id=f"rec:{position_id}:{generated_at[:10]}",
                position_id=position_id,
                user_id=str(position_row["user_id"]),
                effective_at=generated_at,
                action="no_action",
                confidence=0.32,
                rationale="Reason: insufficient market, signal, or profile data to refresh the position.",
                warning_flags=["insufficient-data"],
                suggested_size_action="hold",
            )

        summary = replace(
            summary,
            current_stop=adaptive_target_set.stop_loss if adaptive_target_set else summary.current_stop,
            last_recommendation=recommendation.action,
            last_recommendation_confidence=recommendation.confidence,
            last_recommendation_reason=recommendation.rationale,
            warning_flags=recommendation.warning_flags,
        )
        self._upsert_position_row(connection, summary, str(position_row["strategy_name"]), generated_at)
        self._store_position_recommendation(
            connection,
            recommendation,
            summary,
            market_snapshot.market_regime if market_snapshot is not None else "MIXED",
            generated_at,
        )
        return summary

    def add_position_event(
        self,
        *,
        position_id: str,
        event_type: str,
        quantity: float = 0.0,
        price: float | None = None,
        fees: float = 0.0,
        executed_at: str | None = None,
        notes: str = "",
        metadata: dict[str, Any] | None = None,
        source: str = "user",
    ) -> dict[str, Any]:
        metadata = metadata or {}
        normalized_event_type = str(event_type or "").strip().upper()
        allowed_event_types = {
            "OPEN",
            "ADD",
            "REDUCE",
            "CLOSE",
            "UPDATE_STOP",
            "UPDATE_TARGETS",
            "MANUAL_NOTE",
            "SYSTEM_RECOMMENDATION",
        }
        if normalized_event_type not in allowed_event_types:
            raise ValueError(f"Unsupported event_type: {event_type!r}")
        ensure_non_negative_number(fees, "fees")
        event_ts = parse_timestamp(executed_at or now_iso()) or datetime.utcnow()
        created_at = now_iso()
        with self.connect() as connection:
            position_row = connection.execute("SELECT * FROM open_positions WHERE id = ?", (position_id,)).fetchone()
            if position_row is None:
                raise ValueError(f"Position not found: {position_id}")
            current_market_price = (
                self._latest_close(str(position_row["ticker"]), connection)
                or float(position_row["current_price"] or position_row["average_entry_price"])
            )
            if normalized_event_type in {"OPEN", "ADD", "REDUCE"}:
                ensure_positive_number(quantity, "quantity")
                if price is None:
                    raise ValueError(f"price is required for {normalized_event_type} events.")
                ensure_positive_number(price, "price")
            elif normalized_event_type == "CLOSE":
                quantity = quantity if quantity and quantity > 0 else float(position_row["current_quantity"])
                ensure_positive_number(quantity, "quantity")
                price = current_market_price if price is None else price
                ensure_positive_number(price, "price")
            elif normalized_event_type == "UPDATE_STOP":
                stop_value = metadata.get("stop", price)
                if stop_value is None:
                    raise ValueError("A stop value is required for UPDATE_STOP events.")
                metadata = {**metadata, "stop": float(stop_value)}
                price = float(stop_value)
                ensure_positive_number(price, "price")
            elif normalized_event_type == "UPDATE_TARGETS" and not metadata.get("targets"):
                raise ValueError("A targets payload is required for UPDATE_TARGETS events.")
            event = PositionEvent(
                event_id=f"event:{uuid4().hex[:12]}",
                position_id=position_id,
                ticker=str(position_row["ticker"]),
                side=str(position_row["side"]),
                event_type=normalized_event_type,
                quantity=float(quantity),
                price=float(price) if price is not None else None,
                fees=float(fees),
                executed_at=event_ts,
                source=str(source),
                linked_signal_id=str(position_row["signal_id_origin"]),
                metadata=metadata,
                notes=notes,
            )
            connection.execute(
                """
                INSERT INTO position_events (
                    id, position_id, ticker, side, event_type, quantity, price, fees, executed_at, source,
                    linked_signal_id, metadata_json, notes, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.position_id,
                    event.ticker,
                    event.side,
                    event.event_type,
                    event.quantity,
                    event.price,
                    event.fees,
                    event.executed_at.isoformat(),
                    event.source,
                    event.linked_signal_id,
                    json_dumps(event.metadata),
                    event.notes,
                    created_at,
                ),
            )
            refreshed_row = connection.execute("SELECT * FROM open_positions WHERE id = ?", (position_id,)).fetchone()
            if refreshed_row is not None:
                self._refresh_position_row(connection, refreshed_row, generated_at=created_at)
            connection.commit()
            return self.get_position_detail(position_id, connection=connection)

    def _store_position_recommendation(
        self,
        connection: sqlite3.Connection,
        recommendation: PositionRecommendation,
        position: PositionSummary,
        regime: str,
        generated_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO position_recommendations (
                id, position_id, effective_at, action, confidence, suggested_add_qty, suggested_reduce_qty,
                suggested_stop, suggested_target_1, suggested_target_2, rationale, warning_flags_json,
                suggested_zone_low, suggested_zone_high, created_at, suggested_target_3, suggested_size_action, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(position_id, effective_at) DO UPDATE SET
                action = excluded.action,
                confidence = excluded.confidence,
                suggested_add_qty = excluded.suggested_add_qty,
                suggested_reduce_qty = excluded.suggested_reduce_qty,
                suggested_stop = excluded.suggested_stop,
                suggested_target_1 = excluded.suggested_target_1,
                suggested_target_2 = excluded.suggested_target_2,
                rationale = excluded.rationale,
                warning_flags_json = excluded.warning_flags_json,
                suggested_zone_low = excluded.suggested_zone_low,
                suggested_zone_high = excluded.suggested_zone_high,
                suggested_target_3 = excluded.suggested_target_3,
                suggested_size_action = excluded.suggested_size_action,
                updated_at = excluded.updated_at
            """,
            (
                recommendation.recommendation_id,
                recommendation.position_id,
                recommendation.effective_at,
                recommendation.action,
                recommendation.confidence,
                recommendation.suggested_add_qty,
                recommendation.suggested_reduce_qty,
                recommendation.suggested_stop,
                recommendation.suggested_target_1,
                recommendation.suggested_target_2,
                recommendation.rationale,
                json_dumps(recommendation.warning_flags),
                recommendation.suggested_zone_low,
                recommendation.suggested_zone_high,
                generated_at,
                recommendation.suggested_target_3,
                recommendation.suggested_size_action,
                generated_at,
            ),
        )
        snapshot = PositionDailySnapshot(
            snapshot_id=f"snapshot:{position.position_id}:{recommendation.effective_at[:10]}",
            position_id=position.position_id,
            snapshot_date=parse_date(recommendation.effective_at) or datetime.utcnow().date(),
            close_price=position.mark_price or position.average_entry_price,
            current_quantity=position.current_quantity,
            average_entry_price=position.average_entry_price,
            market_value=position.gross_exposure,
            unrealized_pnl=position.unrealized_pnl,
            realized_pnl_to_date=position.realized_pnl,
            total_pnl=position.total_pnl,
            distance_to_stop_pct=position.distance_to_stop_pct,
            distance_to_target_1_pct=position.distance_to_target_1_pct,
            distance_to_target_2_pct=position.distance_to_target_2_pct,
            regime=regime,
            action_recommendation=recommendation.action,
            recommendation_confidence=recommendation.confidence,
            recommendation_reason=recommendation.rationale,
            max_favorable_excursion=position.max_favorable_excursion,
            max_adverse_excursion=position.max_adverse_excursion,
        )
        connection.execute(
            """
            INSERT INTO position_daily_snapshots (
                id, position_id, snapshot_date, close_price, current_quantity, average_entry_price, market_value,
                unrealized_pnl, realized_pnl_to_date, total_pnl, distance_to_stop_pct, distance_to_target_1_pct,
                distance_to_target_2_pct, regime, action_recommendation, recommendation_confidence,
                recommendation_reason, max_favorable_excursion, max_adverse_excursion, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(position_id, snapshot_date) DO UPDATE SET
                close_price = excluded.close_price,
                current_quantity = excluded.current_quantity,
                average_entry_price = excluded.average_entry_price,
                market_value = excluded.market_value,
                unrealized_pnl = excluded.unrealized_pnl,
                realized_pnl_to_date = excluded.realized_pnl_to_date,
                total_pnl = excluded.total_pnl,
                distance_to_stop_pct = excluded.distance_to_stop_pct,
                distance_to_target_1_pct = excluded.distance_to_target_1_pct,
                distance_to_target_2_pct = excluded.distance_to_target_2_pct,
                regime = excluded.regime,
                action_recommendation = excluded.action_recommendation,
                recommendation_confidence = excluded.recommendation_confidence,
                recommendation_reason = excluded.recommendation_reason,
                max_favorable_excursion = excluded.max_favorable_excursion,
                max_adverse_excursion = excluded.max_adverse_excursion,
                updated_at = excluded.updated_at
            """,
            (
                snapshot.snapshot_id,
                snapshot.position_id,
                snapshot.snapshot_date.isoformat(),
                snapshot.close_price,
                snapshot.current_quantity,
                snapshot.average_entry_price,
                snapshot.market_value,
                snapshot.unrealized_pnl,
                snapshot.realized_pnl_to_date,
                snapshot.total_pnl,
                snapshot.distance_to_stop_pct,
                snapshot.distance_to_target_1_pct,
                snapshot.distance_to_target_2_pct,
                snapshot.regime,
                snapshot.action_recommendation,
                snapshot.recommendation_confidence,
                snapshot.recommendation_reason,
                snapshot.max_favorable_excursion,
                snapshot.max_adverse_excursion,
                generated_at,
                generated_at,
            ),
        )

    def refresh_open_positions(self, *, results_by_ticker: dict[str, TickerPipelineResult], generated_at: str, user_id: str = DEFAULT_USER_ID) -> None:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM open_positions WHERE user_id = ? AND status = 'open'", (user_id,)).fetchall()
            for row in rows:
                result = results_by_ticker.get(str(row["ticker"]))
                self._refresh_position_row(
                    connection,
                    row,
                    generated_at=generated_at,
                    signal=result.latest_prediction if result else None,
                    profile=result.profile if result else None,
                    market_snapshot=result.snapshots[-1] if result and result.snapshots else None,
                )
            connection.commit()

    def get_ticker_detail(self, ticker: str, *, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
        ticker = normalize_ticker(ticker)
        if connection is None:
            with self.connect() as own_connection:
                return self.get_ticker_detail(ticker, connection=own_connection)
        signal = self.get_latest_signal(ticker, connection=connection)
        profile_row = connection.execute("SELECT * FROM ticker_profiles WHERE ticker = ?", (ticker,)).fetchone()
        snapshot_rows = connection.execute(
            "SELECT session_date, open, high, low, close, atr, adx, rsi, support, resistance, trend, market_regime FROM ticker_daily_snapshots WHERE ticker = ? ORDER BY session_date DESC LIMIT 120",
            (ticker,),
        ).fetchall()
        history_rows = connection.execute(
            "SELECT ticker, session_date, direction, outcome_status, realized_return_pct, holding_days, target_1_hit, target_2_hit, stop_hit FROM signal_history WHERE ticker = ? ORDER BY session_date DESC LIMIT 60",
            (ticker,),
        ).fetchall()
        target_set = self.get_target_set("signal", signal.signal_id, "signal_original", connection=connection) if signal else None
        latest_prediction = signal.as_dict() if signal else None
        if latest_prediction and target_set:
            latest_prediction["targets"] = [level.as_dict() for level in self._target_set_to_levels(target_set, "original")]
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
                "warning_flags": latest_prediction["warning_flags"],
                "strategy_name": latest_prediction["strategy_name"],
            }
        return {
            "ticker": ticker,
            "summary": summary,
            "latest_prediction": latest_prediction,
            "latest_signal": latest_prediction,
            "targets": target_set.as_dict() if target_set else None,
            "profile": self._row_to_profile(profile_row).as_dict() if profile_row else None,
            "snapshots": [dict(row) for row in reversed(snapshot_rows)],
            "signal_history": [dict(row) for row in history_rows],
        }

    def list_open_positions(self, user_id: str = DEFAULT_USER_ID, *, connection: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        if connection is None:
            with self.connect() as own_connection:
                return self.list_open_positions(user_id, connection=own_connection)
        rows = connection.execute("SELECT * FROM open_positions WHERE user_id = ? AND status = 'open' ORDER BY updated_at DESC", (user_id,)).fetchall()
        payloads = []
        for row in rows:
            original_target_set = self.get_target_set("position", str(row["id"]), "position_original", connection=connection)
            adaptive_target_set = self.get_target_set("position", str(row["id"]), "position_adaptive", connection=connection)
            summary = self._row_to_position_summary(
                row,
                self._target_set_to_levels(original_target_set, "original") if original_target_set else [],
                self._target_set_to_levels(adaptive_target_set, "adaptive") if adaptive_target_set else [],
            ).as_dict()
            summary["strategy_name"] = str(row["strategy_name"])
            summary["created_at"] = str(row["created_at"])
            summary["updated_at"] = str(row["updated_at"])
            payloads.append(summary)
        return payloads

    def get_position_detail(self, position_id: str, *, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
        if connection is None:
            with self.connect() as own_connection:
                return self.get_position_detail(position_id, connection=own_connection)
        row = connection.execute("SELECT * FROM open_positions WHERE id = ?", (position_id,)).fetchone()
        if row is None:
            raise ValueError(f"Position not found: {position_id}")
        original_target_set = self.get_target_set("position", position_id, "position_original", connection=connection)
        adaptive_target_set = self.get_target_set("position", position_id, "position_adaptive", connection=connection)
        summary = self._row_to_position_summary(
            row,
            self._target_set_to_levels(original_target_set, "original") if original_target_set else [],
            self._target_set_to_levels(adaptive_target_set, "adaptive") if adaptive_target_set else [],
        )
        events = self._load_position_events(position_id, connection)
        recommendations = connection.execute("SELECT * FROM position_recommendations WHERE position_id = ? ORDER BY effective_at DESC LIMIT 60", (position_id,)).fetchall()
        signal = self.get_signal_by_id(summary.signal_id_origin, connection=connection)
        chart_rows = connection.execute(
            "SELECT session_date, open, high, low, close FROM ticker_daily_snapshots WHERE ticker = ? AND session_date >= ? ORDER BY session_date",
            (summary.ticker, summary.opened_at.date().isoformat()),
        ).fetchall()
        return {
            "position": summary.as_dict()
            | {
                "strategy_name": str(row["strategy_name"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            },
            "origin_signal": signal.as_dict() if signal else None,
            "original_targets": original_target_set.as_dict() if original_target_set else None,
            "adaptive_targets": adaptive_target_set.as_dict() if adaptive_target_set else None,
            "events": [event.as_dict() for event in events],
            "recommendations": [dict(item) | {"warning_flags": json.loads(item["warning_flags_json"])} for item in recommendations],
            "chart": [dict(item) for item in chart_rows],
        }

    def build_dashboard_bundle(self, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
        with self.connect() as connection:
            watchlist = self.list_active_tickers(user_id)
            settings = self.get_ui_preferences(user_id)
            latest_run = connection.execute("SELECT completed_at, summary_json FROM backtest_runs ORDER BY completed_at DESC LIMIT 1").fetchone()
            generated_at = latest_run["completed_at"] if latest_run else now_iso()
            latest_summary = json.loads(latest_run["summary_json"]) if latest_run and latest_run["summary_json"] else {}
            tickers = {ticker: self.get_ticker_detail(ticker, connection=connection) for ticker in watchlist}
            signals = [payload["latest_prediction"] for payload in tickers.values() if payload["latest_prediction"]]
            study_watchlist = [payload["summary"] for payload in tickers.values() if payload["summary"]]
            open_positions = self.list_open_positions(user_id, connection=connection)
            positions = {item["position"]["position_id"]: item for item in (self.get_position_detail(row["position_id"], connection=connection) for row in open_positions)}
            signal_history = connection.execute("SELECT ticker, session_date, direction, outcome_status, realized_return_pct, holding_days FROM signal_history ORDER BY session_date DESC LIMIT 150").fetchall()
            position_events = connection.execute("SELECT position_id, ticker, event_type, quantity, price, executed_at, notes FROM position_events ORDER BY executed_at DESC LIMIT 150").fetchall()
            position_recommendations = connection.execute(
                """
                SELECT position_id, effective_at, action, confidence, rationale, suggested_size_action
                FROM position_recommendations
                ORDER BY effective_at DESC
                LIMIT 150
                """
            ).fetchall()
        overview = {
            "tracked_tickers": len(study_watchlist),
            "long_count": sum(1 for row in signals if row.get("direction") == "long"),
            "short_count": sum(1 for row in signals if row.get("direction") == "short"),
            "neutral_count": sum(1 for row in signals if row.get("direction") == "neutral"),
            "high_confidence_count": sum(1 for row in signals if (row.get("confidence_score") or 0) >= 0.72),
            "avg_confidence": round(sum((row.get("confidence_score") or 0) for row in signals) / len(signals), 4) if signals else 0.0,
            "open_positions": len(open_positions),
            "total_unrealized_pnl": round(sum(float(item.get("unrealized_pnl", 0.0)) for item in open_positions), 4),
            "total_realized_pnl": round(sum(float(item.get("realized_pnl", 0.0)) for item in open_positions), 4),
            "positions_requiring_action": sum(1 for item in open_positions if item.get("last_recommendation") in {"add", "reduce", "close"}),
            "generated_at": generated_at,
        }
        return {
            "generated_at": generated_at,
            "capabilities": {
                "mode": "static-snapshot",
                "write": False,
                "refresh": False,
                "auth_mode": "none",
            },
            "market_context": latest_summary.get("market_context", {}),
            "architecture": {
                "selected": "netlify-firestore-github-actions",
                "frontend": "Netlify static SPA",
                "batch": "GitHub Actions daily Python job",
                "storage": "SQLite for local development, Firestore as hosted cloud persistence",
            },
            "overview": overview,
            "study_watchlist": study_watchlist,
            "signals": sorted(signals, key=lambda row: (row.get("direction") == "neutral", -(row.get("confidence_score") or 0), row.get("ticker"))),
            "open_positions": open_positions,
            "tickers": tickers,
            "positions": positions,
            "history": {
                "signals": [dict(row) for row in signal_history],
                "position_events": [dict(row) for row in position_events],
                "position_recommendations": [dict(row) for row in position_recommendations],
            },
            "settings": settings,
        }

    def export_table_rows(self, table_name: str) -> list[dict[str, Any]]:
        import re
        if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
            raise ValueError(f"Invalid table name: {table_name}")
        with self.connect() as connection:
            rows = connection.execute(f"SELECT * FROM {table_name}").fetchall()
        payloads = [dict(row) for row in rows]
        for item in payloads:
            for key, value in list(item.items()):
                if key.endswith("_json") and isinstance(value, str):
                    try:
                        item[key] = json.loads(value)
                    except json.JSONDecodeError:
                        pass
        return payloads
