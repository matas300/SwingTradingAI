from datetime import datetime

import pytest

from swing_trading.models import FeatureSnapshot, PositionEvent, PredictionRecord, ProfileSnapshot, TargetLevel, TargetSetRecord
from swing_trading.position_lifecycle import rebuild_position_summary
from swing_trading.position_policy import recommend_position_action


def make_feature(*, close_vs_ema21_atr: float, adx: float = 26.0, rsi: float = 56.0) -> FeatureSnapshot:
    return FeatureSnapshot(
        ticker="AAPL",
        session_date=datetime(2026, 3, 30).date(),
        open=109.0,
        high=112.0,
        low=108.0,
        close=110.0,
        volume=1_000_000.0,
        atr=2.0,
        adx=adx,
        rsi=rsi,
        ema_fast=109.5,
        ema_slow=108.8,
        sma50=106.0,
        sma200=100.0,
        support=98.0,
        resistance=121.0,
        recent_high=112.5,
        recent_low=104.0,
        volume_ratio=1.2,
        volatility_20d=0.22,
        drawdown_63d=-0.04,
        relative_strength_1m=0.05,
        relative_strength_3m=0.08,
        close_vs_ema21_atr=close_vs_ema21_atr,
        close_to_support_atr=2.0,
        close_to_resistance_atr=2.5,
        breakout="bullish",
        trend="UP",
        market_regime="MIXED",
    )


def make_profile(*, reliability_score: float = 0.78, insufficient_data: bool = False, mean_target_error: float = 0.05) -> ProfileSnapshot:
    return ProfileSnapshot(
        ticker="AAPL",
        sample_size=24,
        closed_signal_count=24,
        long_win_rate=0.64,
        short_win_rate=0.48,
        volatility_rolling=0.22,
        atr_rolling=2.0,
        recent_drawdown=-0.04,
        mean_target_error=mean_target_error,
        mean_mae=0.02,
        mean_mfe=0.06,
        avg_days_to_target=6.0,
        avg_days_to_stop=4.0,
        long_effectiveness=0.64,
        short_effectiveness=0.48,
        dominant_regime="MIXED",
        confidence_floor=0.55,
        target_aggression=1.0,
        target_shrink_factor=1.0,
        reliability_score=reliability_score,
        insufficient_data=insufficient_data,
        trend_persistence=0.7,
        gap_behavior=0.1,
        setup_win_rate=0.58,
        regime_distribution={"MIXED": 1.0},
    )


def make_prediction(*, direction: str = "long", confidence_score: float = 0.82, stop_loss: float = 98.0) -> PredictionRecord:
    return PredictionRecord(
        prediction_id="signal:test",
        ticker="AAPL",
        session_date=datetime(2026, 3, 30).date(),
        direction=direction,
        entry_low=99.0,
        entry_high=101.0,
        stop_loss=stop_loss,
        confidence_score=confidence_score,
        risk_reward=2.4,
        holding_horizon_days=8,
        regime="MIXED",
        reliability_label="High reliability",
        rationale={"summary": "test"},
        warning_flags=[],
        top_factors=[],
        profile_version="test-profile",
        strategy_id="adaptive-swing-v2",
        generated_at="2026-03-30T00:00:00Z",
        setup_name="trend-follow",
    )


def make_target_set(*, scope: str, owner_type: str, owner_id: str, side: str, stop_loss: float = 98.0) -> TargetSetRecord:
    return TargetSetRecord(
        target_id=f"targets:{owner_id}:{scope}",
        owner_type=owner_type,
        owner_id=owner_id,
        scope=scope,
        side=side,
        reference_entry_price=100.0,
        average_entry_price=100.0,
        stop_loss=stop_loss,
        target_1=115.0,
        target_2=125.0,
        optional_target_3=130.0,
        probabilistic_target=120.0,
        risk_reward=2.0,
        confidence_score=0.8,
        holding_horizon_days=8,
        rationale={"summary": "original"},
        warning_flags=["gap-risk"],
        generated_at="2026-03-30T00:00:00Z",
        version_tag="test",
        ticker_symbol="AAPL",
    )


def make_position(
    *,
    side: str = "long",
    mark_price: float = 110.0,
    stop: float = 98.0,
    target_1: float = 115.0,
    target_2: float = 125.0,
    target_3: float = 130.0,
) -> tuple:
    opened_at = datetime(2026, 3, 24, 10, 0, 0)
    event = PositionEvent(
        event_id="event-open",
        position_id="position:test",
        user_id="user:test",
        ticker="AAPL",
        side=side,
        event_type="OPEN",
        quantity=10.0,
        price=100.0,
        fees=0.0,
        executed_at=opened_at,
        source="user",
        linked_signal_id="signal:test",
        metadata={},
        notes="",
        created_at=opened_at.isoformat(),
    )
    original_levels = [
        TargetLevel(kind="target_1", price=target_1, probability=0.6, distance_atr=5.0, rationale="t1", scope="original", version=1, reference_price=100.0),
        TargetLevel(kind="target_2", price=target_2, probability=0.5, distance_atr=10.0, rationale="t2", scope="original", version=1, reference_price=100.0),
        TargetLevel(kind="target_3", price=target_3, probability=0.4, distance_atr=15.0, rationale="t3", scope="original", version=1, reference_price=100.0),
    ]
    adaptive_levels = [TargetLevel(kind=item.kind, price=item.price, probability=item.probability, distance_atr=item.distance_atr, rationale=item.rationale, scope="adaptive", version=item.version, reference_price=item.reference_price) for item in original_levels]
    return rebuild_position_summary(
        position_id="position:test",
        user_id="user:test",
        ticker="AAPL",
        strategy_id="adaptive-swing-v2",
        signal_id_origin="signal:test",
        side=side,
        opened_at=opened_at,
        events=[event],
        original_targets=original_levels,
        adaptive_targets=adaptive_levels,
        original_stop=stop,
        current_stop=stop,
        mark_price=mark_price,
        as_of=datetime(2026, 3, 30, 16, 0, 0),
        price_history=[{"high": 112.0, "low": 97.0, "close": 109.0}],
        last_recommendation="maintain",
        last_recommendation_confidence=0.71,
        last_recommendation_reason="trend intact",
        base_notes="",
    )


def test_recommend_position_action_adds_when_setup_remains_aligned():
    position = make_position(mark_price=110.0, stop=98.0, target_1=125.0, target_2=135.0)
    signal = make_prediction(direction="long", confidence_score=0.84, stop_loss=98.0)
    profile = make_profile()
    market = make_feature(close_vs_ema21_atr=0.6, adx=27.0, rsi=58.0)
    original_targets = make_target_set(scope="position_original", owner_type="position", owner_id="position:test", side="long")
    adaptive_targets = make_target_set(scope="position_adaptive", owner_type="position", owner_id="position:test", side="long")

    recommendation = recommend_position_action(
        position=position,
        signal=signal,
        profile=profile,
        market_snapshot=market,
        original_targets=original_targets,
        adaptive_targets=adaptive_targets,
        effective_at="2026-03-30T16:00:00Z",
    )

    assert recommendation.action == "add"
    assert recommendation.suggested_add_qty == pytest.approx(2.5)
    assert recommendation.suggested_size_action == "add 2.5"
    assert recommendation.suggested_zone_low < recommendation.suggested_zone_high
    assert "aligned" in recommendation.rationale.lower()


def test_recommend_position_action_reduces_when_target_is_near_and_momentum_is_extended():
    position = make_position(mark_price=119.0, stop=98.0, target_1=120.0, target_2=130.0)
    signal = make_prediction(direction="long", confidence_score=0.83, stop_loss=98.0)
    profile = make_profile()
    market = make_feature(close_vs_ema21_atr=1.6, adx=16.0, rsi=67.0)
    original_targets = make_target_set(scope="position_original", owner_type="position", owner_id="position:test", side="long")
    adaptive_targets = make_target_set(scope="position_adaptive", owner_type="position", owner_id="position:test", side="long")

    recommendation = recommend_position_action(
        position=position,
        signal=signal,
        profile=profile,
        market_snapshot=market,
        original_targets=original_targets,
        adaptive_targets=adaptive_targets,
        effective_at="2026-03-30T16:00:00Z",
    )

    assert recommendation.action == "reduce"
    assert recommendation.suggested_reduce_qty == pytest.approx(2.5)
    assert recommendation.suggested_size_action == "reduce 2.5"
    assert "target 1" in recommendation.rationale.lower()


def test_recommend_position_action_closes_when_stop_is_too_close():
    position = make_position(mark_price=100.0, stop=99.5, target_1=115.0, target_2=125.0)
    signal = make_prediction(direction="long", confidence_score=0.81, stop_loss=99.5)
    profile = make_profile()
    market = make_feature(close_vs_ema21_atr=0.3, adx=24.0, rsi=54.0)
    original_targets = make_target_set(scope="position_original", owner_type="position", owner_id="position:test", side="long", stop_loss=99.5)
    adaptive_targets = make_target_set(scope="position_adaptive", owner_type="position", owner_id="position:test", side="long", stop_loss=99.5)

    recommendation = recommend_position_action(
        position=position,
        signal=signal,
        profile=profile,
        market_snapshot=market,
        original_targets=original_targets,
        adaptive_targets=adaptive_targets,
        effective_at="2026-03-30T16:00:00Z",
    )

    assert recommendation.action == "close"
    assert recommendation.suggested_reduce_qty == pytest.approx(position.current_quantity)
    assert recommendation.suggested_size_action == "close all"
    assert "stop" in recommendation.rationale.lower()
