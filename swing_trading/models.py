from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from typing import Any, Literal

SignalDirection = Literal['long', 'short', 'neutral']
PositionSide = Literal['long', 'short']
PositionEventType = Literal['OPEN', 'ADD', 'REDUCE', 'CLOSE', 'UPDATE_STOP', 'UPDATE_TARGETS', 'MANUAL_NOTE', 'SYSTEM_RECOMMENDATION']
RecommendationAction = Literal['add', 'maintain', 'reduce', 'close', 'no_action']
RiskMode = Literal['RISK_ON', 'MIXED', 'RISK_OFF']
SourceType = Literal['user', 'system', 'import']


def _serialize(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if is_dataclass(value):
        return _serialize(asdict(value))
    return value


def dataclass_to_dict(instance: Any) -> dict[str, Any]:
    return dict(_serialize(asdict(instance)))


@dataclass(frozen=True)
class ScannerConfig:
    tickers: tuple[str, ...]
    daily_period: str = '2y'
    daily_interval: str = '1d'
    account_size: float = 10_000.0
    risk_per_trade: float = 0.01
    chart_points: int = 120
    history_window: int = 160
    profile_lookback: int = 110
    signal_horizon_days: int = 12


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
        return dataclass_to_dict(self)


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
    gap_pct: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


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
    trend_persistence: float = 0.5
    gap_behavior: float = 0.0
    setup_win_rate: float = 0.5
    target_overshoot_rate: float = 0.0
    target_undershoot_rate: float = 0.0
    confidence_calibration_error: float = 0.15
    regime_distribution: dict[str, float] = field(default_factory=dict)

    @property
    def setup_specific_win_rate(self) -> float:
        return self.setup_win_rate

    @property
    def average_time_to_target(self) -> float | None:
        return self.avg_days_to_target

    @property
    def average_time_to_stop(self) -> float | None:
        return self.avg_days_to_stop

    @property
    def setup_specific_win_rate(self) -> float:
        return self.setup_win_rate

    def as_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(frozen=True)
class TargetLevel:
    kind: str
    price: float
    probability: float | None
    distance_atr: float
    rationale: str
    scope: str = 'study'
    version: int = 1
    reference_price: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(frozen=True)
class TargetSetRecord:
    target_id: str
    owner_type: str
    owner_id: str
    scope: str
    side: PositionSide | SignalDirection
    reference_entry_price: float | None
    average_entry_price: float | None
    stop_loss: float | None
    target_1: float | None
    target_2: float | None
    optional_target_3: float | None
    probabilistic_target: float | None
    risk_reward: float | None
    confidence_score: float
    holding_horizon_days: int
    rationale: dict[str, Any]
    warning_flags: list[str]
    generated_at: str
    version_tag: str
    ticker_symbol: str = ''

    @property
    def ticker(self) -> str:
        if self.ticker_symbol:
            return self.ticker_symbol
        owner = self.owner_id.replace('signal:', '').replace('position:', '')
        return owner.split(':')[0] if ':' in owner else owner

    @property
    def entry_reference_price(self) -> float | None:
        return self.reference_entry_price

    @property
    def average_entry_reference(self) -> float | None:
        return self.average_entry_price

    @property
    def target_3(self) -> float | None:
        return self.optional_target_3

    @property
    def holding_horizon_estimate(self) -> int:
        return self.holding_horizon_days

    @property
    def version_label(self) -> str:
        return self.version_tag

    def as_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


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
    strategy_id: str = 'adaptive-swing-v2'
    signal_id: str = ''
    generated_at: str = ''
    setup_name: str = 'adaptive-swing-v2'
    setup_quality: str = 'balanced'

    def __post_init__(self) -> None:
        if not self.signal_id:
            object.__setattr__(self, 'signal_id', self.prediction_id)
        if not self.generated_at:
            object.__setattr__(self, 'generated_at', f'{self.session_date.isoformat()}T21:00:00Z')
        if not self.setup_name:
            object.__setattr__(self, 'setup_name', self.strategy_id)

    @property
    def strategy_name(self) -> str:
        return self.setup_name

    @property
    def entry_reference_price(self) -> float | None:
        return self.entry_high if self.direction == 'long' else self.entry_low

    def as_dict(self) -> dict[str, Any]:
        payload = dataclass_to_dict(self)
        if not payload.get('signal_id'):
            payload['signal_id'] = self.signal_id or self.prediction_id
        payload['strategy_name'] = self.strategy_name
        payload['entry_reference_price'] = self.entry_reference_price
        return payload


SignalRecord = PredictionRecord


@dataclass(frozen=True)
class SignalVersionRecord:
    version_id: str
    signal_id: str
    version_tag: str
    generated_at: str
    confidence_score: float
    rationale: dict[str, Any]
    warning_flags: list[str]
    top_factors: list[dict[str, Any]]
    targets: list[TargetLevel]

    def as_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


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
    prediction_confidence: float = 0.0
    setup_name: str = 'adaptive-swing-v2'
    signal_history_id: str = ''
    signal_version_id: str = ''
    signal_id: str = ''

    def __post_init__(self) -> None:
        if not self.signal_id:
            object.__setattr__(self, 'signal_id', self.prediction_id)

    @property
    def predicted_confidence(self) -> float:
        return self.prediction_confidence

    def as_dict(self) -> dict[str, Any]:
        payload = dataclass_to_dict(self)
        payload.setdefault('signal_history_id', self.signal_history_id or f'signal-history:{self.prediction_id}')
        payload.setdefault('signal_version_id', self.signal_version_id or self.prediction_id)
        payload.setdefault('signal_id', self.signal_id or self.prediction_id)
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
    signal_versions: list[SignalVersionRecord] = field(default_factory=list)
    signal_history: list[SignalOutcome] = field(default_factory=list)
    target_revisions: list[TargetSetRecord] = field(default_factory=list)
    next_earnings_date: date | None = None
    earnings_warning: str | None = None


@dataclass(frozen=True)
class PositionEventRecord:
    event_id: str
    position_id: str
    user_id: str
    ticker: str
    side: PositionSide
    event_type: PositionEventType
    quantity: float | None
    price: float | None
    fees: float
    executed_at: datetime
    source: SourceType
    linked_signal_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    notes: str = ''
    created_at: str = ''

    def as_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


PositionEvent = PositionEventRecord


@dataclass(frozen=True)
class PositionState:
    position_id: str
    user_id: str
    ticker: str
    strategy_id: str
    signal_id_origin: str
    side: PositionSide
    status: str
    initial_entry_price: float
    average_entry_price: float
    initial_quantity: float
    current_quantity: float
    opened_at: datetime
    closed_at: datetime | None
    current_stop: float | None
    original_stop: float | None
    targets_from_original_signal: list[TargetLevel]
    current_adaptive_targets: list[TargetLevel]
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    gross_exposure: float
    holding_days: int
    max_favorable_excursion: float
    max_adverse_excursion: float
    distance_to_stop_pct: float | None
    distance_to_target_1_pct: float | None
    distance_to_target_2_pct: float | None
    mark_price: float | None
    last_recommendation: str | None = None
    last_recommendation_confidence: float | None = None
    last_recommendation_reason: str | None = None
    warning_flags: list[str] = field(default_factory=list)
    notes: str = ''

    @property
    def last_price(self) -> float | None:
        return self.mark_price

    @property
    def market_value(self) -> float:
        return abs((self.mark_price or self.average_entry_price) * self.current_quantity)

    @property
    def strategy_name(self) -> str:
        return self.strategy_id

    def as_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


PositionSummary = PositionState


@dataclass(frozen=True)
class PositionRecommendation:
    recommendation_id: str
    position_id: str
    user_id: str
    effective_at: str
    action: RecommendationAction
    confidence: float
    rationale: str
    warning_flags: list[str]
    suggested_add_qty: float | None = None
    suggested_reduce_qty: float | None = None
    suggested_stop: float | None = None
    suggested_target_1: float | None = None
    suggested_target_2: float | None = None
    suggested_target_3: float | None = None
    suggested_zone_low: float | None = None
    suggested_zone_high: float | None = None
    suggested_size_action: str = 'hold'

    def as_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


PositionRecommendationRecord = PositionRecommendation


@dataclass(frozen=True)
class PositionDailySnapshot:
    snapshot_id: str
    position_id: str
    snapshot_date: str
    close_price: float
    current_quantity: float
    average_entry_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl_to_date: float
    total_pnl: float
    distance_to_stop_pct: float | None
    distance_to_target_1_pct: float | None
    distance_to_target_2_pct: float | None
    regime: str
    action_recommendation: RecommendationAction
    recommendation_confidence: float
    recommendation_reason: str
    max_favorable_excursion: float
    max_adverse_excursion: float
    user_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


PositionSnapshot = PositionDailySnapshot
PositionSnapshotRecord = PositionDailySnapshot
