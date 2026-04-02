from datetime import date

from swing_trading.models import FeatureSnapshot, ProfileSnapshot
from swing_trading.signal_engine import generate_prediction, make_factor


def make_feature(**overrides):
    base = {
        "ticker": "NVDA",
        "session_date": date(2026, 3, 26),
        "open": 100.0,
        "high": 104.0,
        "low": 99.0,
        "close": 103.0,
        "volume": 1_000_000.0,
        "atr": 2.0,
        "adx": 28.0,
        "rsi": 60.0,
        "ema_fast": 102.5,
        "ema_slow": 101.5,
        "sma50": 98.0,
        "sma200": 90.0,
        "support": 99.0,
        "resistance": 108.0,
        "recent_high": 107.0,
        "recent_low": 95.0,
        "volume_ratio": 1.3,
        "volatility_20d": 0.28,
        "drawdown_63d": -0.06,
        "relative_strength_1m": 0.04,
        "relative_strength_3m": 0.09,
        "close_vs_ema21_atr": 0.75,
        "close_to_support_atr": 2.0,
        "close_to_resistance_atr": 2.5,
        "breakout": "bullish",
        "trend": "UP",
        "market_regime": "RISK_ON",
    }
    base.update(overrides)
    return FeatureSnapshot(**base)


def make_profile(**overrides):
    base = {
        "ticker": "NVDA",
        "sample_size": 20,
        "closed_signal_count": 20,
        "long_win_rate": 0.62,
        "short_win_rate": 0.48,
        "volatility_rolling": 0.28,
        "atr_rolling": 2.0,
        "recent_drawdown": -0.06,
        "mean_target_error": 0.04,
        "mean_mae": 0.02,
        "mean_mfe": 0.05,
        "avg_days_to_target": 6.0,
        "avg_days_to_stop": 4.0,
        "long_effectiveness": 0.62,
        "short_effectiveness": 0.48,
        "dominant_regime": "RISK_ON",
        "confidence_floor": 0.5,
        "target_aggression": 1.0,
        "target_shrink_factor": 0.92,
        "reliability_score": 0.74,
        "insufficient_data": False,
    }
    base.update(overrides)
    return ProfileSnapshot(**base)


def test_long_signal_produces_signed_levels():
    feature = make_feature()
    profile = make_profile()

    prediction, targets = generate_prediction(feature, profile, profile_version="test")

    target_1 = next(target for target in targets if target.kind == "target_1")
    assert prediction.direction == "long"
    assert prediction.stop_loss is not None and prediction.stop_loss < feature.close
    assert target_1.price > feature.close
    assert prediction.risk_reward is not None and prediction.risk_reward > 0


def test_short_signal_produces_signed_levels():
    feature = make_feature(
        close=95.0,
        high=97.0,
        low=93.0,
        ema_fast=95.5,
        ema_slow=96.2,
        sma50=100.0,
        support=90.0,
        resistance=98.0,
        volume_ratio=1.2,
        rsi=39.0,
        breakout="bearish",
        trend="DOWN",
        market_regime="RISK_OFF",
        relative_strength_1m=-0.05,
        close_vs_ema21_atr=-0.8,
    )
    profile = make_profile(short_win_rate=0.61, target_shrink_factor=0.95)

    prediction, targets = generate_prediction(feature, profile, profile_version="test")

    target_1 = next(target for target in targets if target.kind == "target_1")
    assert prediction.direction == "short"
    assert prediction.stop_loss is not None and prediction.stop_loss > feature.close
    assert target_1.price < feature.close
    assert prediction.risk_reward is not None and prediction.risk_reward > 0


def test_make_factor():
    # Test standard case
    factor = make_factor("Trend", 1.23, "Primary trend is up.")
    assert factor == {"name": "Trend", "contribution": 1.23, "detail": "Primary trend is up."}

    # Test negative contribution
    factor_neg = make_factor("RSI", -0.12, "Oversold")
    assert factor_neg == {"name": "RSI", "contribution": -0.12, "detail": "Oversold"}

    # Test exact integer
    factor_int = make_factor("Volume", 2.0, "High volume")
    assert factor_int == {"name": "Volume", "contribution": 2.0, "detail": "High volume"}

    # Test empty strings
    factor_empty = make_factor("", 0.0, "")
    assert factor_empty == {"name": "", "contribution": 0.0, "detail": ""}
