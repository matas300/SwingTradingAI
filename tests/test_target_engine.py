from datetime import date, datetime

import pytest

from swing_trading.models import FeatureSnapshot, PositionState, PredictionRecord, ProfileSnapshot, TargetLevel, TargetSetRecord
from swing_trading.target_engine import adaptive_position_targets, signal_target_set


def make_feature(*, market_regime: str = "MIXED") -> FeatureSnapshot:
    return FeatureSnapshot(
        ticker="AAPL",
        session_date=date(2026, 3, 30),
        open=109.0,
        high=112.0,
        low=108.0,
        close=110.0,
        volume=1_000_000.0,
        atr=2.0,
        adx=25.0,
        rsi=55.0,
        ema_fast=109.6,
        ema_slow=108.9,
        sma50=107.0,
        sma200=100.0,
        support=98.0,
        resistance=121.0,
        recent_high=113.0,
        recent_low=105.0,
        volume_ratio=1.2,
        volatility_20d=0.24,
        drawdown_63d=-0.05,
        relative_strength_1m=0.04,
        relative_strength_3m=0.08,
        close_vs_ema21_atr=0.5,
        close_to_support_atr=2.0,
        close_to_resistance_atr=2.5,
        breakout="bullish",
        trend="UP",
        market_regime=market_regime,
    )


def make_prediction(*, direction: str = "long") -> PredictionRecord:
    return PredictionRecord(
        prediction_id="signal:test",
        ticker="AAPL",
        session_date=date(2026, 3, 30),
        direction=direction,
        entry_low=99.0,
        entry_high=101.0,
        stop_loss=98.0,
        confidence_score=0.81,
        risk_reward=2.5,
        holding_horizon_days=8,
        regime="MIXED",
        reliability_label="High reliability",
        rationale={"summary": "test"},
        warning_flags=["gap-risk"],
        top_factors=[],
        profile_version="test",
        strategy_id="adaptive-swing-v2",
        generated_at="2026-03-30T00:00:00Z",
        setup_name="trend-follow",
    )


def make_profile(*, target_shrink_factor: float = 1.0, target_aggression: float = 1.0, reliability_score: float = 0.78) -> ProfileSnapshot:
    return ProfileSnapshot(
        ticker="AAPL",
        sample_size=20,
        closed_signal_count=20,
        long_win_rate=0.64,
        short_win_rate=0.52,
        volatility_rolling=0.24,
        atr_rolling=2.0,
        recent_drawdown=-0.05,
        mean_target_error=0.04,
        mean_mae=0.02,
        mean_mfe=0.06,
        avg_days_to_target=6.0,
        avg_days_to_stop=4.0,
        long_effectiveness=0.64,
        short_effectiveness=0.52,
        dominant_regime="MIXED",
        confidence_floor=0.55,
        target_aggression=target_aggression,
        target_shrink_factor=target_shrink_factor,
        reliability_score=reliability_score,
        insufficient_data=False,
        trend_persistence=0.7,
        gap_behavior=0.1,
        setup_win_rate=0.58,
        regime_distribution={"MIXED": 1.0},
    )


def make_position(
    *,
    side: str = "long",
    mark_price: float = 110.0,
    stop: float = 98.0,
    average_entry_price: float | None = None,
    target_1: float = 115.0,
    target_2: float = 125.0,
    target_3: float = 130.0,
) -> PositionState:
    if side == "short":
        targets = [
            TargetLevel(kind="target_1", price=target_1, probability=0.6, distance_atr=5.0, rationale="t1", scope="adaptive", version=1, reference_price=120.0),
            TargetLevel(kind="target_2", price=target_2, probability=0.5, distance_atr=10.0, rationale="t2", scope="adaptive", version=1, reference_price=120.0),
            TargetLevel(kind="target_3", price=target_3, probability=0.4, distance_atr=15.0, rationale="t3", scope="adaptive", version=1, reference_price=120.0),
        ]
        initial_entry_price = 120.0
    else:
        targets = [
            TargetLevel(kind="target_1", price=target_1, probability=0.6, distance_atr=5.0, rationale="t1", scope="adaptive", version=1, reference_price=100.0),
            TargetLevel(kind="target_2", price=target_2, probability=0.5, distance_atr=10.0, rationale="t2", scope="adaptive", version=1, reference_price=100.0),
            TargetLevel(kind="target_3", price=target_3, probability=0.4, distance_atr=15.0, rationale="t3", scope="adaptive", version=1, reference_price=100.0),
        ]
        initial_entry_price = 100.0
    average_entry = initial_entry_price if average_entry_price is None else average_entry_price
    return PositionState(
        position_id="position:test",
        user_id="user:test",
        ticker="AAPL",
        strategy_id="adaptive-swing-v2",
        signal_id_origin="signal:test",
        side=side,
        status="open",
        initial_entry_price=initial_entry_price,
        average_entry_price=average_entry,
        initial_quantity=10.0,
        current_quantity=10.0,
        opened_at=datetime(2026, 3, 24, 10, 0, 0),
        closed_at=None,
        current_stop=stop,
        original_stop=stop,
        targets_from_original_signal=targets,
        current_adaptive_targets=targets,
        realized_pnl=0.0,
        unrealized_pnl=(mark_price - initial_entry_price) if side == "long" else (initial_entry_price - mark_price),
        total_pnl=(mark_price - initial_entry_price) if side == "long" else (initial_entry_price - mark_price),
        gross_exposure=abs(mark_price * 10.0),
        holding_days=6,
        max_favorable_excursion=0.23,
        max_adverse_excursion=0.03,
        distance_to_stop_pct=((mark_price - stop) / mark_price) if side == "long" else ((stop - mark_price) / mark_price),
        distance_to_target_1_pct=((target_1 - mark_price) / mark_price) if side == "long" else ((mark_price - target_1) / mark_price),
        distance_to_target_2_pct=((target_2 - mark_price) / mark_price) if side == "long" else ((mark_price - target_2) / mark_price),
        mark_price=mark_price,
        last_recommendation="maintain",
        last_recommendation_confidence=0.71,
        last_recommendation_reason="trend intact",
        warning_flags=[],
        notes="",
    )


def make_target_set(*, scope: str, side: str, stop_loss: float = 98.0) -> TargetSetRecord:
    return TargetSetRecord(
        target_id=f"targets:{scope}",
        owner_type="position",
        owner_id="position:test",
        scope=scope,
        side=side,
        reference_entry_price=100.0,
        average_entry_price=105.0,
        stop_loss=stop_loss,
        target_1=115.0,
        target_2=125.0,
        optional_target_3=130.0,
        probabilistic_target=120.0,
        risk_reward=2.0,
        confidence_score=0.8,
        holding_horizon_days=8,
        rationale={"summary": scope},
        warning_flags=["gap-risk"],
        generated_at="2026-03-30T00:00:00Z",
        version_tag="test",
        ticker_symbol="AAPL",
    )


@pytest.mark.parametrize(
    ("direction", "expected_entry"),
    [("long", 101.0), ("short", 99.0)],
)
def test_signal_target_set_uses_the_correct_entry_anchor(direction, expected_entry):
    prediction = make_prediction(direction=direction)
    levels = [
        TargetLevel(kind="target_1", price=115.0, probability=0.6, distance_atr=5.0, rationale="t1", scope="study", version=1, reference_price=100.0),
        TargetLevel(kind="target_2", price=125.0, probability=0.5, distance_atr=10.0, rationale="t2", scope="study", version=1, reference_price=100.0),
        TargetLevel(kind="target_3", price=130.0, probability=0.4, distance_atr=15.0, rationale="t3", scope="study", version=1, reference_price=100.0),
    ]

    target_set = signal_target_set(prediction, levels)

    assert target_set.reference_entry_price == pytest.approx(expected_entry)
    assert target_set.average_entry_price == pytest.approx(expected_entry)
    assert target_set.target_1 == pytest.approx(115.0)
    assert target_set.target_2 == pytest.approx(125.0)
    assert target_set.target_3 == pytest.approx(130.0)


def test_adaptive_position_targets_reanchors_to_average_entry_and_calibrates_levels():
    position = make_position(average_entry_price=105.0)
    prediction = make_prediction(direction="long")
    profile = make_profile(target_shrink_factor=1.0, target_aggression=1.0)
    market = make_feature()
    original_targets = make_target_set(scope="position_original", side="long")

    target_set = adaptive_position_targets(
        position=position,
        signal=prediction,
        profile=profile,
        market_snapshot=market,
        original_targets=original_targets,
    )

    assert target_set.reference_entry_price == pytest.approx(100.0)
    assert target_set.average_entry_price == pytest.approx(105.0)
    assert target_set.stop_loss == pytest.approx(98.0)
    assert target_set.target_1 == pytest.approx(120.0)
    assert target_set.target_2 == pytest.approx(130.0)
    assert target_set.target_3 is None
    assert target_set.probabilistic_target == pytest.approx(125.0)
    assert target_set.risk_reward == pytest.approx(2.1429, rel=1e-4)
    assert target_set.warning_flags == ["gap-risk"]


def test_adaptive_position_targets_flips_levels_for_short_positions():
    position = make_position(side="short", mark_price=110.0, stop=124.0, target_1=110.0, target_2=100.0, target_3=95.0)
    prediction = make_prediction(direction="short")
    profile = make_profile(target_shrink_factor=1.0, target_aggression=1.0)
    market = make_feature()
    original_targets = TargetSetRecord(
        target_id="targets:position_original",
        owner_type="position",
        owner_id="position:test",
        scope="position_original",
        side="short",
        reference_entry_price=120.0,
        average_entry_price=120.0,
        stop_loss=124.0,
        target_1=110.0,
        target_2=100.0,
        optional_target_3=95.0,
        probabilistic_target=105.0,
        risk_reward=2.0,
        confidence_score=0.8,
        holding_horizon_days=8,
        rationale={"summary": "short"},
        warning_flags=["gap-risk"],
        generated_at="2026-03-30T00:00:00Z",
        version_tag="test",
        ticker_symbol="AAPL",
    )

    target_set = adaptive_position_targets(
        position=position,
        signal=prediction,
        profile=profile,
        market_snapshot=market,
        original_targets=original_targets,
    )

    assert target_set.side == "short"
    assert target_set.stop_loss == pytest.approx(121.3)
    assert target_set.target_1 == pytest.approx(110.0)
    assert target_set.target_2 == pytest.approx(100.0)
    assert target_set.probabilistic_target == pytest.approx(105.0)
