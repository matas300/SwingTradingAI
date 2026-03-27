from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Literal

SignalDirection = Literal["long", "short", "neutral"]
RiskMode = Literal["RISK_ON", "MIXED", "RISK_OFF"]


@dataclass(frozen=True)
class ScannerConfig:
    tickers: tuple[str, ...]
    daily_period: str = "2y"
    daily_interval: str = "1d"
    account_size: float = 10_000.0
    risk_per_trade: float = 0.01
    chart_points: int = 120
    history_window: int = 140
    profile_lookback: int = 90
    signal_horizon_days: int = 10


@dataclass(frozen=True)
class MarketContext:
    benchmark_trend: str
    growth_trend: str
    benchmark_close: float
    benchmark_sma50: float
    growth_close: float
    growth_sma50: float
    vix_close: float
    vix_sma20: float
    risk_mode: RiskMode
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FeatureSnapshot:
    ticker: str
    session_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    atr: float
    adx: float
    rsi: float
    ema_fast: float
    ema_slow: float
    sma50: float
    sma200: float | None
    support: float | None
    resistance: float | None
    recent_high: float | None
    recent_low: float | None
    volume_ratio: float
    volatility_20d: float
    drawdown_63d: float
    relative_strength_1m: float
    relative_strength_3m: float
    close_vs_ema21_atr: float
    close_to_support_atr: float | None
    close_to_resistance_atr: float | None
    breakout: str | None
    trend: str
    market_regime: RiskMode

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["session_date"] = self.session_date.isoformat()
        return payload


@dataclass(frozen=True)
class ProfileSnapshot:
    ticker: str
    sample_size: int
    closed_signal_count: int
    long_win_rate: float
    short_win_rate: float
    volatility_rolling: float
    atr_rolling: float
    recent_drawdown: float
    mean_target_error: float
    mean_mae: float
    mean_mfe: float
    avg_days_to_target: float | None
    avg_days_to_stop: float | None
    long_effectiveness: float
    short_effectiveness: float
    dominant_regime: str
    confidence_floor: float
    target_aggression: float
    target_shrink_factor: float
    reliability_score: float
    insufficient_data: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TargetLevel:
    kind: str
    price: float
    probability: float | None
    distance_atr: float
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PredictionRecord:
    prediction_id: str
    ticker: str
    session_date: date
    direction: SignalDirection
    entry_low: float | None
    entry_high: float | None
    stop_loss: float | None
    confidence_score: float
    risk_reward: float | None
    holding_horizon_days: int
    regime: RiskMode
    reliability_label: str
    rationale: dict[str, Any]
    warning_flags: list[str]
    top_factors: list[dict[str, Any]]
    profile_version: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["session_date"] = self.session_date.isoformat()
        return payload


@dataclass(frozen=True)
class SignalOutcome:
    prediction_id: str
    ticker: str
    session_date: date
    direction: SignalDirection
    regime: RiskMode
    outcome_status: str
    target_1_hit: bool
    target_2_hit: bool
    stop_hit: bool
    max_adverse_excursion: float
    max_favorable_excursion: float
    realized_return_pct: float
    holding_days: int
    target_error: float

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["session_date"] = self.session_date.isoformat()
        return payload


@dataclass(frozen=True)
class TickerPipelineResult:
    ticker: str
    market_context: MarketContext
    snapshots: list[FeatureSnapshot]
    profile: ProfileSnapshot
    latest_prediction: PredictionRecord
    latest_targets: list[TargetLevel]
    historical_predictions: list[PredictionRecord]
    historical_targets: dict[str, list[TargetLevel]]
    signal_history: list[SignalOutcome]
    next_earnings_date: date | None = None
    earnings_warning: str | None = None
