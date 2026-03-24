from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from swing_trading_ai_improved import (
    DEFAULT_TICKERS,
    ScannerConfig,
    TOP_100_US_TICKERS,
    build_console_summary_frame,
    format_pct,
    format_price,
    run_scan,
)


APP_DIR = Path(__file__).parent
STATIC_DIR = APP_DIR / "static"
HISTORY_DIR = APP_DIR / "history"
HISTORY_LOG = HISTORY_DIR / "scan_history.jsonl"
SCAN_RESULTS_CSV = HISTORY_DIR / "scan_results.csv"
SCAN_RESULTS_DB = HISTORY_DIR / "scan_history.sqlite3"
COMPACT_RESULTS_THRESHOLD = 20
TOP_100_UNIVERSE_NAME = "Top 100 USA"

HISTORY_DIR.mkdir(exist_ok=True)


class ScanRequest(BaseModel):
    tickers: list[str] = Field(default_factory=lambda: list(DEFAULT_TICKERS))
    daily_period: str = "3mo"
    account_size: float = 10_000.0
    risk_per_trade: float = 0.01
    news_lookback_days: int = 5
    news_enabled: bool = False


class AutoScanRequest(BaseModel):
    daily_period: str = "3mo"
    account_size: float = 10_000.0
    risk_per_trade: float = 0.01
    news_lookback_days: int = 5
    news_enabled: bool = False


app = FastAPI(title="Swing Trading AI")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def serialize_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def sanitize(value: Any) -> Any:
    if is_dataclass(value):
        return sanitize(asdict(value))
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize(item) for item in value]
    return serialize_scalar(value)


def serialize_market_context(context: Any, macro_news: Any) -> dict[str, Any]:
    return {
        "market": sanitize(context),
        "macro_news": sanitize(macro_news),
    }


def move_pct(entry: float | None, level: float | None) -> float | None:
    if entry is None or level is None or pd.isna(entry) or pd.isna(level) or entry == 0:
        return None
    return abs(float(level) - float(entry)) / abs(float(entry)) * 100


def serialize_setup(setup: Any, *, compact: bool = False) -> dict[str, Any]:
    macro_headlines = [] if compact else sanitize(setup.macro_news.headlines)
    company_headlines = [] if compact else sanitize(setup.company_news.headlines)
    price_chart = [] if compact else sanitize(setup.price_chart)

    return {
        "ticker": setup.ticker,
        "analysis_date": setup.analysis_date.isoformat(),
        "decision": {
            "technical_signal": setup.technical_signal,
            "technical_confidence": setup.technical_confidence,
            "operational_signal": setup.signal,
            "operational_confidence": setup.confidence,
            "grade": setup.grade,
        },
        "pricing": {
            "entry": serialize_scalar(setup.entry),
            "stop": serialize_scalar(setup.stop),
            "target": serialize_scalar(setup.target),
            "risk_per_share": serialize_scalar(setup.risk_per_share),
            "reward_per_share": serialize_scalar(setup.reward_per_share),
            "loss_pct": serialize_scalar(move_pct(setup.entry, setup.stop)),
            "gain_pct": serialize_scalar(move_pct(setup.entry, setup.target)),
            "position_size": setup.position_size,
            "size_multiplier": setup.position_multiplier,
            "entry_label": format_price(setup.entry),
            "stop_label": format_price(setup.stop),
            "target_label": format_price(setup.target),
            "risk_label": format_price(setup.risk_per_share),
            "reward_label": format_price(setup.reward_per_share),
        },
        "technical": {
            "trend": setup.daily.trend,
            "rsi": round(setup.daily.rsi, 2),
            "adx": round(setup.daily.adx, 2),
            "atr": round(setup.daily.atr, 2),
            "relative_strength_1m": setup.daily.relative_strength_1m,
            "relative_strength_1m_label": format_pct(setup.daily.relative_strength_1m),
            "support": serialize_scalar(setup.daily.support),
            "resistance": serialize_scalar(setup.daily.resistance),
            "volume_label": setup.daily.volume_label,
            "reasons": list(setup.technical_reasons),
            "warnings": list(setup.technical_warnings),
        },
        "macro": {
            "market_mode": setup.market.risk_mode,
            "macro_news_level": setup.macro_news.level,
            "macro_news_score": round(setup.macro_news.net_risk_score, 2),
            "macro_themes": list(setup.macro_news.matched_themes),
            "macro_headlines": macro_headlines,
            "market_warnings": list(setup.market.warnings),
        },
        "company": {
            "news_level": setup.company_news.level,
            "news_score": round(setup.company_news.net_risk_score, 2),
            "themes": list(setup.company_news.matched_themes),
            "headlines": company_headlines,
        },
        "earnings": sanitize(setup.earnings),
        "charts": {
            "price": price_chart,
        },
        "operational": {
            "reasons": list(setup.reasons),
            "warnings": list(setup.warnings),
            "commentary": setup.commentary,
        },
    }


def summary_records(summary: pd.DataFrame) -> list[dict[str, Any]]:
    if summary.empty:
        return []
    records = summary.where(pd.notnull(summary), None).to_dict(orient="records")
    return [sanitize(record) for record in records]


def console_summary_records(console_summary: pd.DataFrame) -> list[dict[str, Any]]:
    if console_summary.empty:
        return []
    return sanitize(console_summary.to_dict(orient="records"))


def build_history_setup_record(setup: Any) -> dict[str, Any]:
    return {
        "ticker": setup.ticker,
        "analysis_date": setup.analysis_date.isoformat(),
        "signal": setup.signal,
        "technical_signal": setup.technical_signal,
        "confidence": round(setup.confidence, 4),
        "technical_confidence": round(setup.technical_confidence, 4),
        "grade": setup.grade,
        "market_mode": setup.market.risk_mode,
        "macro_news_level": setup.macro_news.level,
        "company_news_level": setup.company_news.level,
        "entry": serialize_scalar(setup.entry),
        "stop": serialize_scalar(setup.stop),
        "target": serialize_scalar(setup.target),
        "position_size": setup.position_size,
        "close": round(setup.daily.close, 4),
        "rsi": round(setup.daily.rsi, 2),
        "adx": round(setup.daily.adx, 2),
        "next_earnings_date": serialize_scalar(setup.earnings.next_earnings_date),
        "days_to_earnings": setup.earnings.days_to_earnings,
    }


def build_snapshot_payload(
    *,
    generated_at: datetime,
    request: Any,
    market_context: Any,
    macro_news: Any,
    setups: list[Any],
    failures: list[str],
) -> dict[str, Any]:
    analysis_session_date = (
        max(setup.analysis_date for setup in setups).isoformat()
        if setups
        else generated_at.date().isoformat()
    )

    request_payload = request.model_dump() if hasattr(request, "model_dump") else request

    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "analysis_session_date": analysis_session_date,
        "request": sanitize(request_payload),
        "overview": {
            "long_count": sum(1 for setup in setups if setup.signal == "LONG"),
            "short_count": sum(1 for setup in setups if setup.signal == "SHORT"),
            "no_trade_count": sum(1 for setup in setups if setup.signal == "NO TRADE"),
        },
        "context": serialize_market_context(market_context, macro_news),
        "setups": [build_history_setup_record(setup) for setup in setups],
        "failures": failures,
    }


def append_snapshot_to_history(snapshot: dict[str, Any]) -> None:
    with HISTORY_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=True))
        handle.write("\n")


def read_history_snapshots() -> list[dict[str, Any]]:
    if not HISTORY_LOG.exists():
        return []

    snapshots: list[dict[str, Any]] = []
    with HISTORY_LOG.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                snapshots.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    return snapshots


def build_history_response(tickers: tuple[str, ...], limit: int = 90) -> dict[str, list[dict[str, Any]]]:
    by_ticker: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    for snapshot in read_history_snapshots():
        generated_at = snapshot.get("generated_at")
        for item in snapshot.get("setups", []):
            ticker = str(item.get("ticker") or "").upper()
            if tickers and ticker not in tickers:
                continue

            session_date = item.get("analysis_date") or snapshot.get("analysis_session_date")
            if not session_date:
                continue

            normalized = {
                "session_date": session_date,
                "generated_at": generated_at,
                "close": item.get("close"),
                "operational_signal": item.get("signal"),
                "operational_confidence": item.get("confidence"),
                "technical_signal": item.get("technical_signal"),
                "technical_confidence": item.get("technical_confidence"),
                "market_mode": item.get("market_mode"),
                "macro_news_level": item.get("macro_news_level"),
                "company_news_level": item.get("company_news_level"),
                "entry": item.get("entry"),
                "stop": item.get("stop"),
                "target": item.get("target"),
                "position_size": item.get("position_size"),
                "grade": item.get("grade"),
            }

            existing = by_ticker[ticker].get(session_date)
            if existing is None or str(existing.get("generated_at") or "") <= str(generated_at or ""):
                by_ticker[ticker][session_date] = normalized

    history: dict[str, list[dict[str, Any]]] = {}
    for ticker in tickers:
        daily_points = sorted(by_ticker.get(ticker, {}).values(), key=lambda item: item["session_date"])
        history[ticker] = daily_points[-limit:]
    return history


def overview_payload(setups: list[Any]) -> dict[str, int]:
    return {
        "long_count": sum(1 for setup in setups if setup.signal == "LONG"),
        "short_count": sum(1 for setup in setups if setup.signal == "SHORT"),
        "no_trade_count": sum(1 for setup in setups if setup.signal == "NO TRADE"),
    }


def ensure_scan_storage() -> None:
    scan_runs_sql = """
        CREATE TABLE IF NOT EXISTS scan_runs (
            run_id TEXT PRIMARY KEY,
            generated_at TEXT NOT NULL,
            analysis_session_date TEXT NOT NULL,
            scan_mode TEXT NOT NULL,
            universe_name TEXT NOT NULL,
            ticker_count INTEGER NOT NULL,
            long_count INTEGER NOT NULL,
            short_count INTEGER NOT NULL,
            no_trade_count INTEGER NOT NULL,
            failure_count INTEGER NOT NULL,
            news_enabled INTEGER NOT NULL,
            daily_period TEXT NOT NULL,
            account_size REAL NOT NULL,
            risk_per_trade REAL NOT NULL,
            news_lookback_days INTEGER NOT NULL,
            request_json TEXT NOT NULL,
            failures_json TEXT NOT NULL
        )
    """
    scan_setups_sql = """
        CREATE TABLE IF NOT EXISTS scan_setups (
            run_id TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            analysis_session_date TEXT NOT NULL,
            scan_mode TEXT NOT NULL,
            universe_name TEXT NOT NULL,
            ticker_count INTEGER NOT NULL,
            news_enabled INTEGER NOT NULL,
            failure_count INTEGER NOT NULL,
            Ticker TEXT NOT NULL,
            AnalysisDate TEXT,
            Signal TEXT,
            TechnicalSignal TEXT,
            Grade TEXT,
            ConfidencePct REAL,
            TechnicalConfidencePct REAL,
            TrendDaily TEXT,
            MarketMode TEXT,
            MacroNewsLevel TEXT,
            MacroNewsScore REAL,
            MacroThemes TEXT,
            CompanyNewsLevel TEXT,
            CompanyNewsScore REAL,
            CompanyThemes TEXT,
            NextEarningsDate TEXT,
            DaysToEarnings REAL,
            Entry REAL,
            Stop REAL,
            Target REAL,
            RiskPerShare REAL,
            PositionSize REAL,
            SizeMultiplier REAL,
            DailyRSI REAL,
            DailyADX REAL,
            DailyATR REAL,
            RS1MvsSPY REAL
        )
    """

    def ensure_table_schema(
        connection: sqlite3.Connection,
        *,
        table_name: str,
        create_sql: str,
        required_columns: set[str],
    ) -> None:
        columns = {
            str(row[1])
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if not columns:
            connection.execute(create_sql)
            return
        if required_columns.issubset(columns):
            return

        backup_name = f"{table_name}_legacy_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        connection.execute(f"ALTER TABLE {table_name} RENAME TO {backup_name}")
        connection.execute(create_sql)

    with sqlite3.connect(SCAN_RESULTS_DB) as connection:
        ensure_table_schema(
            connection,
            table_name="scan_runs",
            create_sql=scan_runs_sql,
            required_columns={"run_id", "generated_at", "scan_mode", "news_enabled", "request_json"},
        )
        ensure_table_schema(
            connection,
            table_name="scan_setups",
            create_sql=scan_setups_sql,
            required_columns={"run_id", "generated_at", "Ticker", "Signal", "news_enabled"},
        )
        connection.commit()


def build_persistence_frame(
    *,
    summary: pd.DataFrame,
    run_id: str,
    generated_at: datetime,
    analysis_session_date: str,
    scan_mode: str,
    universe_name: str,
    ticker_count: int,
    news_enabled: bool,
    failure_count: int,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    frame = summary.copy()
    frame.insert(0, "run_id", run_id)
    frame.insert(1, "generated_at", generated_at.isoformat(timespec="seconds"))
    frame.insert(2, "analysis_session_date", analysis_session_date)
    frame.insert(3, "scan_mode", scan_mode)
    frame.insert(4, "universe_name", universe_name)
    frame.insert(5, "ticker_count", ticker_count)
    frame.insert(6, "news_enabled", bool(news_enabled))
    frame.insert(7, "failure_count", failure_count)
    return frame


def persist_scan_results(
    *,
    generated_at: datetime,
    analysis_session_date: str,
    request_payload: dict[str, Any],
    scan_mode: str,
    universe_name: str,
    setups: list[Any],
    failures: list[str],
    summary: pd.DataFrame,
) -> dict[str, Any]:
    run_id = str(uuid4())
    overview = overview_payload(setups)
    ticker_count = len(request_payload.get("tickers", []))
    news_enabled = bool(request_payload.get("news_enabled", False))
    frame = build_persistence_frame(
        summary=summary,
        run_id=run_id,
        generated_at=generated_at,
        analysis_session_date=analysis_session_date,
        scan_mode=scan_mode,
        universe_name=universe_name,
        ticker_count=ticker_count,
        news_enabled=news_enabled,
        failure_count=len(failures),
    )

    ensure_scan_storage()
    with sqlite3.connect(SCAN_RESULTS_DB) as connection:
        connection.execute(
            """
            INSERT INTO scan_runs (
                run_id, generated_at, analysis_session_date, scan_mode, universe_name,
                ticker_count, long_count, short_count, no_trade_count, failure_count,
                news_enabled, daily_period, account_size, risk_per_trade,
                news_lookback_days, request_json, failures_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                generated_at.isoformat(timespec="seconds"),
                analysis_session_date,
                scan_mode,
                universe_name,
                ticker_count,
                overview["long_count"],
                overview["short_count"],
                overview["no_trade_count"],
                len(failures),
                int(news_enabled),
                str(request_payload.get("daily_period", "")),
                float(request_payload.get("account_size", 0.0)),
                float(request_payload.get("risk_per_trade", 0.0)),
                int(request_payload.get("news_lookback_days", 0)),
                json.dumps(sanitize(request_payload), ensure_ascii=True),
                json.dumps(sanitize(failures), ensure_ascii=True),
            ),
        )
        if not frame.empty:
            frame.to_sql("scan_setups", connection, if_exists="append", index=False)
        connection.commit()

    if not frame.empty:
        frame.to_csv(SCAN_RESULTS_CSV, mode="a", header=not SCAN_RESULTS_CSV.exists(), index=False)

    return {
        "run_id": run_id,
        "csv_path": str(SCAN_RESULTS_CSV),
        "db_path": str(SCAN_RESULTS_DB),
        "saved_rows": int(len(frame)),
    }


def history_tickers_for_response(setups: list[Any], *, only_actionable_view: bool = False) -> tuple[str, ...]:
    if only_actionable_view:
        return tuple(dict.fromkeys(setup.ticker for setup in setups if setup.signal != "NO TRADE"))

    if len(setups) <= COMPACT_RESULTS_THRESHOLD:
        return tuple(dict.fromkeys(setup.ticker for setup in setups))

    actionable = tuple(dict.fromkeys(setup.ticker for setup in setups if setup.signal != "NO TRADE"))
    return actionable


def execute_scan(
    *,
    tickers: tuple[str, ...],
    request_payload: dict[str, Any],
    scan_mode: str,
    universe_name: str,
    only_actionable_view: bool = False,
) -> dict[str, Any]:
    config = ScannerConfig(
        tickers=tickers,
        daily_period=str(request_payload["daily_period"]),
        account_size=float(request_payload["account_size"]),
        risk_per_trade=float(request_payload["risk_per_trade"]),
        news_lookback_days=int(request_payload["news_lookback_days"]),
        news_enabled=bool(request_payload.get("news_enabled", False)),
    )

    market_context, macro_news, setups, failures, summary = run_scan(config)
    console_summary = build_console_summary_frame(setups) if setups else pd.DataFrame()
    generated_at = datetime.now()
    request_payload = {
        **request_payload,
        "tickers": list(tickers),
    }
    snapshot = build_snapshot_payload(
        generated_at=generated_at,
        request=request_payload,
        market_context=market_context,
        macro_news=macro_news,
        setups=setups,
        failures=failures,
    )
    append_snapshot_to_history(snapshot)
    storage = persist_scan_results(
        generated_at=generated_at,
        analysis_session_date=snapshot["analysis_session_date"],
        request_payload=request_payload,
        scan_mode=scan_mode,
        universe_name=universe_name,
        setups=setups,
        failures=failures,
        summary=summary,
    )
    compact_mode = only_actionable_view or len(setups) > COMPACT_RESULTS_THRESHOLD
    hidden_waiting_count = sum(1 for setup in setups if setup.signal == "NO TRADE") if compact_mode else 0
    response_history_tickers = history_tickers_for_response(setups, only_actionable_view=only_actionable_view)
    history = build_history_response(response_history_tickers) if response_history_tickers else {}

    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "analysis_session_date": snapshot["analysis_session_date"],
        "request": sanitize(request_payload),
        "context": serialize_market_context(market_context, macro_news),
        "overview": overview_payload(setups),
        "summary": summary_records(summary),
        "console_summary": console_summary_records(console_summary),
        "setups": [
            serialize_setup(setup, compact=compact_mode and setup.signal == "NO TRADE")
            for setup in setups
        ],
        "history": history,
        "failures": failures,
        "storage": storage,
        "ui": {
            "compact_mode": compact_mode,
            "compact_threshold": COMPACT_RESULTS_THRESHOLD,
            "hidden_waiting_count": hidden_waiting_count,
            "only_actionable_view": only_actionable_view,
            "scan_mode": scan_mode,
            "universe_name": universe_name,
            "top_100_count": len(TOP_100_US_TICKERS),
        },
    }


@app.get("/api/defaults")
def defaults() -> dict[str, Any]:
    return {
        "tickers": list(DEFAULT_TICKERS),
        "daily_period": "3mo",
        "account_size": 10_000.0,
        "risk_per_trade": 0.01,
        "news_lookback_days": 5,
        "news_enabled": False,
        "top_100_count": len(TOP_100_US_TICKERS),
        "top_100_universe_name": TOP_100_UNIVERSE_NAME,
    }


@app.post("/api/scan")
def scan(request: ScanRequest) -> dict[str, Any]:
    tickers = tuple(dict.fromkeys(ticker.strip().upper() for ticker in request.tickers if ticker.strip()))
    if not tickers:
        tickers = DEFAULT_TICKERS

    return execute_scan(
        tickers=tickers,
        request_payload=request.model_dump(),
        scan_mode="manual",
        universe_name="Custom list",
        only_actionable_view=False,
    )


@app.post("/api/autoscan")
def autoscan(request: AutoScanRequest) -> dict[str, Any]:
    return execute_scan(
        tickers=TOP_100_US_TICKERS,
        request_payload=request.model_dump(),
        scan_mode="autoscan_top_100_usa",
        universe_name=TOP_100_UNIVERSE_NAME,
        only_actionable_view=True,
    )


@app.get("/api/history")
def history(tickers: str = Query("", description="Comma-separated ticker list"), limit: int = 90) -> dict[str, Any]:
    normalized = tuple(
        dict.fromkeys(token.strip().upper() for token in tickers.split(",") if token.strip())
    )
    requested = normalized or DEFAULT_TICKERS
    return {
        "tickers": list(requested),
        "history": build_history_response(requested, limit=max(1, min(limit, 365))),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
