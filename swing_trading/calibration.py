from __future__ import annotations

from collections import Counter
from statistics import mean

from .models import FeatureSnapshot, ProfileSnapshot, SignalOutcome


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def default_profile(ticker: str, latest_feature: FeatureSnapshot | None = None) -> ProfileSnapshot:
    return ProfileSnapshot(
        ticker=ticker,
        sample_size=0,
        closed_signal_count=0,
        long_win_rate=0.5,
        short_win_rate=0.5,
        volatility_rolling=latest_feature.volatility_20d if latest_feature else 0.0,
        atr_rolling=latest_feature.atr if latest_feature else 0.0,
        recent_drawdown=latest_feature.drawdown_63d if latest_feature else 0.0,
        mean_target_error=0.15,
        mean_mae=0.02,
        mean_mfe=0.03,
        avg_days_to_target=None,
        avg_days_to_stop=None,
        long_effectiveness=0.5,
        short_effectiveness=0.5,
        dominant_regime=latest_feature.market_regime if latest_feature else "MIXED",
        confidence_floor=0.56,
        target_aggression=0.9,
        target_shrink_factor=0.88,
        reliability_score=0.42,
        insufficient_data=True,
    )


def reliability_label(score: float, insufficient_data: bool) -> str:
    if insufficient_data:
        return "Insufficient data"
    if score >= 0.78:
        return "High reliability"
    if score >= 0.62:
        return "Medium reliability"
    return "Low reliability"


def build_profile_from_history(
    ticker: str,
    latest_feature: FeatureSnapshot,
    history: list[SignalOutcome],
) -> ProfileSnapshot:
    if not history:
        return default_profile(ticker, latest_feature)

    long_history = [item for item in history if item.direction == "long"]
    short_history = [item for item in history if item.direction == "short"]
    regimes = Counter(item.regime for item in history)
    long_win_rate = len([item for item in long_history if item.outcome_status in {"target_1", "target_2", "open_gain"}]) / len(long_history) if long_history else 0.5
    short_win_rate = len([item for item in short_history if item.outcome_status in {"target_1", "target_2", "open_gain"}]) / len(short_history) if short_history else 0.5
    mean_target_error = mean(item.target_error for item in history)
    mean_mae = mean(item.max_adverse_excursion for item in history)
    mean_mfe = mean(item.max_favorable_excursion for item in history)
    target_days = [item.holding_days for item in history if item.target_1_hit or item.target_2_hit]
    stop_days = [item.holding_days for item in history if item.stop_hit]
    sample_size = len(history)
    avg_win_rate = (long_win_rate + short_win_rate) / 2.0
    sample_bonus = min(sample_size / 40.0, 1.0) * 0.14
    reliability_score = clamp(
        0.40 + sample_bonus + ((avg_win_rate - 0.5) * 0.40) - (abs(mean_target_error) * 0.25),
        0.25,
        0.90,
    )
    target_shrink_factor = clamp(
        1.0 - max(mean_target_error, 0.0) * 1.25 + max(-mean_target_error, 0.0) * 0.20,
        0.72,
        1.12,
    )
    target_aggression = clamp(target_shrink_factor + (reliability_score - 0.5) * 0.15, 0.78, 1.18)
    confidence_floor = clamp(0.50 + max(0.0, 0.60 - reliability_score) * 0.20, 0.48, 0.68)
    insufficient_data = sample_size < 8

    if insufficient_data:
        reliability_score = min(reliability_score, 0.58)
        target_shrink_factor = min(target_shrink_factor, 0.92)
        target_aggression = min(target_aggression, 0.94)

    return ProfileSnapshot(
        ticker=ticker,
        sample_size=sample_size,
        closed_signal_count=sample_size,
        long_win_rate=long_win_rate,
        short_win_rate=short_win_rate,
        volatility_rolling=latest_feature.volatility_20d,
        atr_rolling=latest_feature.atr,
        recent_drawdown=latest_feature.drawdown_63d,
        mean_target_error=mean_target_error,
        mean_mae=mean_mae,
        mean_mfe=mean_mfe,
        avg_days_to_target=mean(target_days) if target_days else None,
        avg_days_to_stop=mean(stop_days) if stop_days else None,
        long_effectiveness=long_win_rate,
        short_effectiveness=short_win_rate,
        dominant_regime=regimes.most_common(1)[0][0] if regimes else latest_feature.market_regime,
        confidence_floor=confidence_floor,
        target_aggression=target_aggression,
        target_shrink_factor=target_shrink_factor,
        reliability_score=reliability_score,
        insufficient_data=insufficient_data,
    )
