from datetime import date, timedelta
import pytest

from swing_trading.calibration import build_profile_from_history, reliability_label, clamp
from swing_trading.models import FeatureSnapshot, SignalOutcome


def make_feature():
    return FeatureSnapshot(
        ticker="AAPL",
        session_date=date(2026, 3, 26),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1_000_000.0,
        atr=1.8,
        adx=24.0,
        rsi=58.0,
        ema_fast=100.7,
        ema_slow=100.1,
        sma50=97.0,
        sma200=91.0,
        support=98.5,
        resistance=105.0,
        recent_high=104.5,
        recent_low=94.0,
        volume_ratio=1.1,
        volatility_20d=0.22,
        drawdown_63d=-0.04,
        relative_strength_1m=0.03,
        relative_strength_3m=0.06,
        close_vs_ema21_atr=0.5,
        close_to_support_atr=1.4,
        close_to_resistance_atr=2.0,
        breakout=None,
        trend="UP",
        market_regime="RISK_ON",
    )


def test_profile_shrinks_targets_when_history_overestimates():
    feature = make_feature()
    history = [
        SignalOutcome(
            prediction_id=f"AAPL:{index}",
            ticker="AAPL",
            session_date=date(2026, 1, 1) + timedelta(days=index),
            direction="long" if index % 2 == 0 else "short",
            regime="RISK_ON",
            outcome_status="open_gain" if index % 3 else "stop",
            target_1_hit=False,
            target_2_hit=False,
            stop_hit=index % 3 == 0,
            max_adverse_excursion=0.03,
            max_favorable_excursion=0.01,
            realized_return_pct=-0.01 if index % 3 == 0 else 0.005,
            holding_days=4,
            target_error=0.12,
        )
        for index in range(10)
    ]

    profile = build_profile_from_history("AAPL", feature, history)

    assert profile.sample_size == 10
    assert profile.insufficient_data is False
    assert profile.target_shrink_factor < 1.0
    assert profile.reliability_score < 0.75


def test_profile_reflects_consistent_wins_and_positive_gap_bias():
    feature = make_feature()
    feature = FeatureSnapshot(
        **{
            **feature.__dict__,
            "gap_pct": 0.04,
        }
    )
    history = [
        SignalOutcome(
            prediction_id=f"AAPL:win-{index}",
            ticker="AAPL",
            session_date=date(2026, 1, 1) + timedelta(days=index),
            direction="long",
            regime="RISK_ON",
            outcome_status="target_1",
            target_1_hit=True,
            target_2_hit=False,
            stop_hit=False,
            max_adverse_excursion=0.01,
            max_favorable_excursion=0.08,
            realized_return_pct=0.03,
            holding_days=5,
            target_error=-0.08,
        )
        for index in range(12)
    ]

    profile = build_profile_from_history("AAPL", feature, history)

    assert profile.insufficient_data is False
    assert profile.long_win_rate == 1.0
    assert profile.short_win_rate == 0.5
    assert profile.setup_specific_win_rate == 1.0
    assert profile.target_shrink_factor > 1.0
    assert profile.average_time_to_target == 5
    assert profile.target_overshoot_rate == 1.0
    assert profile.target_undershoot_rate == 0.0
    assert profile.gap_behavior == 1.5
    assert profile.regime_distribution == {"RISK_ON": 1.0}


def test_clamp_within_bounds():
    assert clamp(5.0, 1.0, 10.0) == 5.0
    assert clamp(0.0, -1.0, 1.0) == 0.0


def test_clamp_below_lower_bound():
    assert clamp(0.5, 1.0, 10.0) == 1.0
    assert clamp(-5.0, -2.0, 2.0) == -2.0


def test_clamp_above_upper_bound():
    assert clamp(15.0, 1.0, 10.0) == 10.0
    assert clamp(5.0, -2.0, 2.0) == 2.0


def test_clamp_equal_to_bounds():
    assert clamp(1.0, 1.0, 10.0) == 1.0
    assert clamp(10.0, 1.0, 10.0) == 10.0
    assert clamp(-2.0, -2.0, 2.0) == -2.0
    assert clamp(2.0, -2.0, 2.0) == 2.0


def test_clamp_with_negative_values():
    assert clamp(-5.0, -10.0, -1.0) == -5.0
    assert clamp(-15.0, -10.0, -1.0) == -10.0
    assert clamp(-0.5, -10.0, -1.0) == -1.0

@pytest.mark.parametrize(
    "score, insufficient_data, expected",
    [
        (0.8, True, "Insufficient data"),
        (0.5, True, "Insufficient data"),
        (0.8, False, "High reliability"),
        (0.75, False, "High reliability"),
        (0.74, False, "Moderate reliability"),
        (0.50, False, "Moderate reliability"),
        (0.49, False, "Low reliability"),
        (0.1, False, "Low reliability"),
    ],
)
def test_reliability_label(score: float, insufficient_data: bool, expected: str):
    assert reliability_label(score, insufficient_data) == expected
