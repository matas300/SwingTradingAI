from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd

from .calibration import build_profile_from_history, default_profile
from .constants import DEFAULT_DB_PATH, DEFAULT_STATIC_EXPORT_PATH, DEFAULT_TICKERS, DEFAULT_USER_ID
from .market_data import add_indicators, build_feature_history, build_market_context, download_prices, get_next_earnings_date
from .models import FeatureSnapshot, MarketContext, PredictionRecord, ScannerConfig, SignalOutcome, TargetLevel, TickerPipelineResult
from .signal_engine import evaluate_prediction, generate_prediction
from .storage import SQLiteStore


def format_price(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.2f}"


def format_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) * 100:+.2f}%"


@dataclass(frozen=True)
class LegacyTradeSetup:
    ticker: str
    analysis_date: date
    technical_signal: str
    technical_confidence: float
    signal: str
    confidence: float
    grade: str
    entry: float | None
    stop: float | None
    target: float | None
    risk_per_share: float | None
    reward_per_share: float | None
    rr_ratio: float | None
    position_size: int
    position_multiplier: float
    daily: object
    market: MarketContext
    macro_news: object
    company_news: object
    earnings: object
    technical_reasons: list[str]
    technical_warnings: list[str]
    reasons: list[str]
    warnings: list[str]
    commentary: str
    price_chart: list[dict]


class NeutralNews:
    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        self.level = "LOW"
        self.net_risk_score = 0.0
        self.matched_themes: tuple[str, ...] = ()
        self.headlines: list[dict] = []
        self.stance = "NEUTRAL"
        self.size_multiplier = 1.0


class EarningsContext:
    def __init__(self, next_earnings_date: date | None) -> None:
        self.next_earnings_date = next_earnings_date
        if next_earnings_date is None:
            self.days_to_earnings = None
            self.label = "Date unavailable"
            self.warning = None
        else:
            days = max((next_earnings_date - datetime.utcnow().date()).days, 0)
            self.days_to_earnings = days
            self.label = f"in {days} days"
            self.warning = "Earnings soon" if days <= 7 else None


class DailySummary:
    def __init__(self, feature: FeatureSnapshot) -> None:
        self.trend = feature.trend
        self.support = feature.support
        self.resistance = feature.resistance
        self.volume_label = "high" if feature.volume_ratio >= 1.15 else "low" if feature.volume_ratio <= 0.85 else "normal"
        self.score = 0
        self.atr = feature.atr
        self.adx = feature.adx
        self.rsi = feature.rsi
        self.ema_fast = feature.ema_fast
        self.ema_slow = feature.ema_slow
        self.close = feature.close
        self.breakout = feature.breakout
        self.relative_strength_1m = feature.relative_strength_1m


def grade_from_confidence(value: float) -> str:
    if value >= 0.82:
        return "A"
    if value >= 0.70:
        return "B"
    if value >= 0.58:
        return "C"
    return "-"


def build_console_summary_frame(setups: list[LegacyTradeSetup]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Ticker": setup.ticker,
                "Signal": setup.signal,
                "Trend": setup.daily.trend,
                "Entry": format_price(setup.entry),
                "Stop": format_price(setup.stop),
                "Target": format_price(setup.target),
                "RSI": round(setup.daily.rsi, 2),
                "ADX": round(setup.daily.adx, 2),
                "RR": round(setup.rr_ratio, 2) if setup.rr_ratio is not None else "-",
            }
            for setup in setups
        ]
    )


def _load_watchlist_from_config(path: str | Path = "config/watchlist.json") -> list[str]:
    config_path = Path(path)
    if not config_path.exists():
        return list(DEFAULT_TICKERS)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    tickers = payload.get("tracked_tickers") or payload.get("tickers") or list(DEFAULT_TICKERS)
    return [str(item).strip().upper() for item in tickers if str(item).strip()]


def analyze_ticker(*, ticker: str, config: ScannerConfig, market_context: MarketContext, benchmark: pd.DataFrame) -> TickerPipelineResult:
    frame = add_indicators(download_prices(ticker, period=config.daily_period, interval=config.daily_interval))
    feature_history = build_feature_history(ticker, frame, benchmark, market_context)
    if len(feature_history) < max(config.profile_lookback, 20):
        raise RuntimeError(f"{ticker}: insufficient confirmed history")

    history_slice = feature_history[-config.history_window:]
    bootstrap_history: list[SignalOutcome] = []
    bootstrap_predictions: list[PredictionRecord] = []
    bootstrap_targets: dict[str, list[TargetLevel]] = {}
    base_profile = default_profile(ticker, history_slice[-1])
    start_index = max(5, len(history_slice) - config.profile_lookback)

    for index in range(start_index, len(history_slice) - 1):
        snapshot = history_slice[index]
        prediction, targets = generate_prediction(snapshot, base_profile, profile_version="bootstrap-v2")
        future_window = history_slice[index + 1 : index + 1 + config.signal_horizon_days]
        outcome = evaluate_prediction(prediction, targets, future_window)
        bootstrap_predictions.append(prediction)
        bootstrap_targets[prediction.signal_id] = targets
        bootstrap_history.append(outcome)

    profile = build_profile_from_history(ticker, history_slice[-1], bootstrap_history)
    latest_snapshot = history_slice[-1]
    latest_prediction, latest_targets = generate_prediction(latest_snapshot, profile, profile_version="adaptive-v2")
    historical_predictions = bootstrap_predictions + [latest_prediction]
    historical_targets = dict(bootstrap_targets)
    historical_targets[latest_prediction.signal_id] = latest_targets
    pending_outcome = SignalOutcome(
        prediction_id=latest_prediction.prediction_id,
        ticker=latest_prediction.ticker,
        session_date=latest_prediction.session_date,
        direction=latest_prediction.direction,
        regime=latest_prediction.regime,
        outcome_status="pending",
        target_1_hit=False,
        target_2_hit=False,
        stop_hit=False,
        max_adverse_excursion=0.0,
        max_favorable_excursion=0.0,
        realized_return_pct=0.0,
        holding_days=0,
        target_error=0.0,
        prediction_confidence=latest_prediction.confidence_score,
        setup_name=latest_prediction.setup_name,
        signal_history_id=f"signal-history:{latest_prediction.signal_id}",
        signal_version_id=latest_prediction.prediction_id,
        signal_id=latest_prediction.signal_id,
    )
    next_earnings_date = get_next_earnings_date(ticker)
    earnings_warning = None
    if next_earnings_date:
        days = max((next_earnings_date - datetime.utcnow().date()).days, 0)
        if days <= 7:
            earnings_warning = f"Earnings in {days} days"

    return TickerPipelineResult(
        ticker=ticker,
        market_context=market_context,
        snapshots=history_slice,
        profile=profile,
        latest_prediction=latest_prediction,
        latest_targets=latest_targets,
        historical_predictions=historical_predictions,
        historical_targets=historical_targets,
        signal_history=bootstrap_history + [pending_outcome],
        next_earnings_date=next_earnings_date,
        earnings_warning=earnings_warning,
    )


def run_pipeline(
    *,
    tickers: list[str] | None = None,
    daily_period: str = "2y",
    database_path: str | Path | None = None,
    export_path: str | Path | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, object]:
    store = SQLiteStore(database_path or os.getenv("DATABASE_PATH", DEFAULT_DB_PATH))
    store.ensure_schema()
    store.seed_defaults(user_id=user_id, tickers=tuple(DEFAULT_TICKERS))

    requested = [ticker.strip().upper() for ticker in (tickers or _load_watchlist_from_config()) if ticker.strip()]
    if tickers is not None:
        store.replace_watchlist(requested, user_id=user_id)
    tracked = sorted(dict.fromkeys(requested + store.list_open_position_tickers(user_id=user_id)))
    config = ScannerConfig(tickers=tuple(tracked), daily_period=daily_period)
    market_context, benchmark = build_market_context(period=daily_period)
    generated_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    results: list[TickerPipelineResult] = []
    failures: list[str] = []

    for ticker in tracked:
        try:
            results.append(analyze_ticker(ticker=ticker, config=config, market_context=market_context, benchmark=benchmark))
        except Exception as exc:
            failures.append(f"{ticker}: {exc}")

    run_id = str(uuid4())
    store.save_pipeline_run(
        run_id=run_id,
        tickers=tracked,
        results=results,
        generated_at=generated_at,
        config_payload={
            "tickers": tracked,
            "daily_period": daily_period,
            "history_window": config.history_window,
            "profile_lookback": config.profile_lookback,
            "signal_horizon_days": config.signal_horizon_days,
        },
        market_context=market_context.as_dict(),
    )
    store.refresh_open_positions(results_by_ticker={item.ticker: item for item in results}, generated_at=generated_at, user_id=user_id)
    bundle = store.build_dashboard_bundle(user_id=user_id)
    export_dashboard_bundle(bundle, export_path or os.getenv("STATIC_EXPORT_PATH", DEFAULT_STATIC_EXPORT_PATH))
    return {
        "run_id": run_id,
        "generated_at": generated_at,
        "tickers": tracked,
        "saved_tickers": len(results),
        "failures": failures,
        "bundle": bundle,
    }


def export_dashboard_bundle(bundle: dict[str, object], path: str | Path) -> None:
    export_target = Path(path)
    export_target.parent.mkdir(parents=True, exist_ok=True)
    export_target.write_text(json.dumps(bundle, ensure_ascii=True, indent=2), encoding="utf-8")


def run_scan_legacy(config: ScannerConfig) -> tuple[MarketContext, NeutralNews, list[LegacyTradeSetup], list[str], pd.DataFrame]:
    market_context, benchmark = build_market_context(period=config.daily_period)
    setups: list[LegacyTradeSetup] = []
    failures: list[str] = []
    for ticker in config.tickers:
        try:
            result = analyze_ticker(ticker=ticker, config=config, market_context=market_context, benchmark=benchmark)
            prediction = result.latest_prediction
            target_1 = next((target for target in result.latest_targets if target.kind == "target_1"), None)
            reference_entry = prediction.entry_reference_price
            risk = abs(result.snapshots[-1].close - prediction.stop_loss) if prediction.stop_loss is not None else None
            reward = abs(target_1.price - result.snapshots[-1].close) if target_1 is not None else None
            feature = result.snapshots[-1]
            daily = DailySummary(feature)
            daily.score = sum(int(abs(item.get("contribution", 0)) >= 0.5) for item in prediction.top_factors)
            signal = prediction.direction.upper() if prediction.direction != "neutral" else "NO TRADE"
            warning_list = list(prediction.warning_flags)
            if result.earnings_warning:
                warning_list.append("earnings-soon")
            setups.append(
                LegacyTradeSetup(
                    ticker=ticker,
                    analysis_date=feature.session_date,
                    technical_signal=signal,
                    technical_confidence=prediction.confidence_score,
                    signal=signal,
                    confidence=prediction.confidence_score,
                    grade=grade_from_confidence(prediction.confidence_score),
                    entry=reference_entry,
                    stop=prediction.stop_loss,
                    target=target_1.price if target_1 is not None else None,
                    risk_per_share=risk,
                    reward_per_share=reward,
                    rr_ratio=prediction.risk_reward,
                    position_size=max(int(config.account_size * config.risk_per_trade / risk), 0) if risk else 0,
                    position_multiplier=prediction.confidence_score if signal != "NO TRADE" else 0.0,
                    daily=daily,
                    market=market_context,
                    macro_news=NeutralNews("MARKET"),
                    company_news=NeutralNews(ticker),
                    earnings=EarningsContext(result.next_earnings_date),
                    technical_reasons=[str(factor["detail"]) for factor in prediction.top_factors],
                    technical_warnings=warning_list,
                    reasons=[str(prediction.rationale["summary"]), str(prediction.rationale["target_reason"])],
                    warnings=warning_list,
                    commentary=str(prediction.rationale["summary"]),
                    price_chart=[{"date": snapshot.session_date.isoformat(), "close": snapshot.close, "sma50": snapshot.sma50, "sma200": snapshot.sma200} for snapshot in result.snapshots[-config.chart_points:]],
                )
            )
        except Exception as exc:
            failures.append(f"{ticker}: {exc}")
    return market_context, NeutralNews("MARKET"), setups, failures, build_console_summary_frame(setups)
