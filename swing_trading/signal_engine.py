from __future__ import annotations

from .calibration import clamp, reliability_label
from .models import FeatureSnapshot, PredictionRecord, ProfileSnapshot, SignalDirection, SignalOutcome, TargetLevel


def make_factor(name: str, contribution: float, detail: str) -> dict[str, float | str]:
    return {
        "name": name,
        "contribution": round(contribution, 3),
        "detail": detail,
    }


def _direction_factors(feature: FeatureSnapshot) -> tuple[list[dict[str, float | str]], list[dict[str, float | str]]]:
    long_factors: list[dict[str, float | str]] = []
    short_factors: list[dict[str, float | str]] = []

    if feature.trend == "UP":
        long_factors.append(make_factor("Trend", 2.0, "Price above 50-day trend with fast EMA support."))
        short_factors.append(make_factor("Trend", -1.2, "Primary trend is not bearish."))
    elif feature.trend == "DOWN":
        short_factors.append(make_factor("Trend", 2.0, "Price below 50-day trend with weak EMA stack."))
        long_factors.append(make_factor("Trend", -1.2, "Primary trend is not bullish."))
    else:
        long_factors.append(make_factor("Trend", -0.5, "Trend is lateral."))
        short_factors.append(make_factor("Trend", -0.5, "Trend is lateral."))

    if feature.breakout == "bullish":
        long_factors.append(make_factor("Breakout", 1.5, "Bullish breakout confirmed with volume."))
    elif feature.breakout == "bearish":
        short_factors.append(make_factor("Breakout", 1.5, "Bearish breakdown confirmed with volume."))

    if feature.market_regime == "RISK_ON":
        long_factors.append(make_factor("Regime", 1.0, "Broad market risk appetite supports longs."))
        short_factors.append(make_factor("Regime", -0.5, "Risk-on backdrop weakens shorts."))
    elif feature.market_regime == "RISK_OFF":
        short_factors.append(make_factor("Regime", 1.0, "Risk-off backdrop supports shorts."))
        long_factors.append(make_factor("Regime", -0.8, "Risk-off backdrop penalizes longs."))
    else:
        long_factors.append(make_factor("Regime", 0.2, "Mixed regime adds only limited support."))
        short_factors.append(make_factor("Regime", 0.2, "Mixed regime adds only limited support."))

    if feature.adx >= 25:
        long_factors.append(make_factor("ADX", 0.8, "Trend strength is above 25."))
        short_factors.append(make_factor("ADX", 0.8, "Trend strength is above 25."))
    elif feature.adx < 18:
        long_factors.append(make_factor("ADX", -0.8, "Trend strength is weak."))
        short_factors.append(make_factor("ADX", -0.8, "Trend strength is weak."))

    if 52 <= feature.rsi <= 68:
        long_factors.append(make_factor("RSI", 0.7, "Momentum is constructive without being overstretched."))
    elif feature.rsi > 74:
        long_factors.append(make_factor("RSI", -0.7, "Momentum is overextended for fresh longs."))
        short_factors.append(make_factor("RSI", 0.3, "Overbought condition may help mean reversion lower."))

    if 32 <= feature.rsi <= 48:
        short_factors.append(make_factor("RSI", 0.7, "Momentum is weak without being deeply oversold."))
    elif feature.rsi < 26:
        short_factors.append(make_factor("RSI", -0.7, "Momentum is stretched for fresh shorts."))
        long_factors.append(make_factor("RSI", 0.3, "Oversold condition may support a rebound."))

    if feature.volume_ratio >= 1.15:
        long_factors.append(make_factor("Volume", 0.5, "Participation is above 20-day average."))
        short_factors.append(make_factor("Volume", 0.5, "Participation is above 20-day average."))
    elif feature.volume_ratio <= 0.85:
        long_factors.append(make_factor("Volume", -0.5, "Participation is light."))
        short_factors.append(make_factor("Volume", -0.5, "Participation is light."))

    if feature.relative_strength_1m > 0:
        long_factors.append(make_factor("Relative strength", 0.7, "Ticker outperformed SPY over one month."))
    else:
        short_factors.append(make_factor("Relative strength", 0.7, "Ticker lagged SPY over one month."))

    if feature.close_to_resistance_atr is not None and feature.close_to_resistance_atr < 0.7:
        long_factors.append(make_factor("Structure", -0.6, "Price is close to nearby resistance."))
    if feature.close_to_support_atr is not None and feature.close_to_support_atr < 0.7:
        short_factors.append(make_factor("Structure", -0.6, "Price is close to nearby support."))

    if abs(feature.close_vs_ema21_atr) > 1.6:
        if feature.close_vs_ema21_atr > 0:
            long_factors.append(make_factor("Extension", -0.7, "Price is extended above EMA21 in ATR terms."))
        else:
            short_factors.append(make_factor("Extension", -0.7, "Price is extended below EMA21 in ATR terms."))

    return long_factors, short_factors


def _baseline_levels(
    feature: FeatureSnapshot,
    direction: SignalDirection,
    aggression: float,
) -> tuple[float | None, float | None, float | None, float | None, float | None, float | None]:
    if direction == "neutral":
        return None, None, None, None, None, None

    atr = max(feature.atr, 0.01)
    regime_factor = 1.08 if feature.market_regime == "RISK_ON" and direction == "long" else 1.0
    if feature.market_regime == "RISK_OFF" and direction == "long":
        regime_factor = 0.90
    if feature.market_regime == "RISK_OFF" and direction == "short":
        regime_factor = 1.08

    base_move_1 = atr * 1.55 * aggression * regime_factor
    base_move_2 = atr * 2.40 * aggression * regime_factor
    entry_low = feature.close - atr * 0.25 if direction == "long" else feature.close
    entry_high = feature.close if direction == "long" else feature.close + atr * 0.25

    if direction == "long":
        stop_loss = min(feature.support if feature.support is not None else feature.close - 1.2 * atr, feature.close - 1.2 * atr)
        raw_target_1 = feature.close + base_move_1
        raw_target_2 = feature.close + base_move_2
        if feature.resistance is not None and feature.resistance > feature.close:
            raw_target_1 = min(raw_target_1, feature.resistance)
            raw_target_2 = max(raw_target_1, min(raw_target_2, feature.resistance + atr))
        probabilistic_target = feature.close + atr * 1.10 * aggression
    else:
        stop_loss = max(feature.resistance if feature.resistance is not None else feature.close + 1.2 * atr, feature.close + 1.2 * atr)
        raw_target_1 = feature.close - base_move_1
        raw_target_2 = feature.close - base_move_2
        if feature.support is not None and feature.support < feature.close:
            raw_target_1 = max(raw_target_1, feature.support)
            raw_target_2 = min(raw_target_1, max(raw_target_2, feature.support - atr))
        probabilistic_target = feature.close - atr * 1.10 * aggression

    return (
        entry_low,
        entry_high,
        stop_loss,
        raw_target_1,
        max(raw_target_2, raw_target_1) if direction == "long" else min(raw_target_2, raw_target_1),
        probabilistic_target,
    )


def generate_prediction(
    feature: FeatureSnapshot,
    profile: ProfileSnapshot,
    *,
    profile_version: str,
) -> tuple[PredictionRecord, list[TargetLevel]]:
    long_factors, short_factors = _direction_factors(feature)
    long_score = sum(float(item["contribution"]) for item in long_factors)
    short_score = sum(float(item["contribution"]) for item in short_factors)
    direction: SignalDirection = "neutral"
    best_score = max(long_score, short_score)
    score_gap = abs(long_score - short_score)

    if best_score >= 2.2 and score_gap >= 0.7:
        direction = "long" if long_score > short_score else "short"

    structural_confidence = clamp(0.43 + max(best_score, 0.0) / 8.5 * 0.34, 0.28, 0.86)
    confidence = clamp(
        0.58 * structural_confidence + 0.42 * profile.reliability_score,
        0.22,
        0.94,
    )
    if profile.insufficient_data:
        confidence = min(confidence, 0.62)
    if direction != "neutral" and confidence < profile.confidence_floor:
        direction = "neutral"

    entry_low = entry_high = stop_loss = target_1 = target_2 = probabilistic_target = None
    targets: list[TargetLevel] = []
    risk_reward = None
    warning_flags: list[str] = []
    aggression = profile.target_aggression * profile.target_shrink_factor

    if direction != "neutral":
        entry_low, entry_high, stop_loss, target_1, target_2, probabilistic_target = _baseline_levels(feature, direction, aggression)
        if target_1 is not None:
            distance_1 = abs(target_1 - feature.close)
            distance_2 = abs(target_2 - feature.close) if target_2 is not None else distance_1
            calibrated_distance_1 = distance_1 * profile.target_shrink_factor
            calibrated_distance_2 = distance_2 * max(profile.target_shrink_factor, 0.85)
            calibrated_prob_distance = abs(probabilistic_target - feature.close) * profile.target_shrink_factor if probabilistic_target is not None else distance_1 * 0.8
            if direction == "long":
                target_1 = feature.close + calibrated_distance_1
                target_2 = feature.close + max(calibrated_distance_2, calibrated_distance_1 * 1.25)
                probabilistic_target = feature.close + calibrated_prob_distance
            else:
                target_1 = feature.close - calibrated_distance_1
                target_2 = feature.close - max(calibrated_distance_2, calibrated_distance_1 * 1.25)
                probabilistic_target = feature.close - calibrated_prob_distance

        risk = abs(feature.close - stop_loss) if stop_loss is not None else None
        reward = abs(target_1 - feature.close) if target_1 is not None else None
        risk_reward = (reward / risk) if risk and reward else None
        if risk_reward is not None and risk_reward < 1.4:
            warning_flags.append("weak-risk-reward")
        if feature.volume_ratio < 0.85:
            warning_flags.append("low-volume")
        if abs(feature.close_vs_ema21_atr) > 1.6:
            warning_flags.append("overextended")
        if profile.target_shrink_factor < 0.92:
            warning_flags.append("historical-overestimation")
        if profile.insufficient_data:
            warning_flags.append("insufficient-data")
        if direction == "long" and feature.market_regime == "RISK_OFF":
            warning_flags.append("counter-regime-long")
        if direction == "short" and feature.market_regime == "RISK_ON":
            warning_flags.append("counter-regime-short")

        atr = max(feature.atr, 0.01)
        targets = [
            TargetLevel(
                kind="target_1",
                price=target_1,
                probability=round(min(confidence + 0.06, 0.94), 4),
                distance_atr=abs(target_1 - feature.close) / atr,
                rationale="Baseline technical objective adjusted by ticker target-error history.",
            ),
            TargetLevel(
                kind="target_2",
                price=target_2,
                probability=round(max(confidence - 0.08, 0.20), 4),
                distance_atr=abs(target_2 - feature.close) / atr,
                rationale="Extended objective gated by regime and profile aggression.",
            ),
            TargetLevel(
                kind="probabilistic_target",
                price=probabilistic_target,
                probability=round(confidence, 4),
                distance_atr=abs(probabilistic_target - feature.close) / atr,
                rationale="Mid-case path used when historical follow-through is moderate.",
            ),
        ]
    else:
        warning_flags.extend(["low-confidence", "stand-aside"])
        if profile.insufficient_data:
            warning_flags.append("insufficient-data")

    factor_pool = long_factors if direction != "short" else short_factors
    sorted_factors = sorted(factor_pool, key=lambda item: abs(float(item["contribution"])), reverse=True)
    horizon = 8 if feature.adx >= 25 else 11
    if profile.avg_days_to_target:
        horizon = round((horizon + profile.avg_days_to_target) / 2)

    rationale = {
        "summary": (
            "Neutral posture due to limited edge after structure and profile calibration."
            if direction == "neutral"
            else f"{direction.title()} bias from trend structure, ATR levels, regime filter, and ticker calibration."
        ),
        "target_reason": "Targets start from ATR plus support/resistance structure, then shrink or expand using historical target error.",
        "regime": feature.market_regime,
        "reliability": reliability_label(profile.reliability_score, profile.insufficient_data),
        "profile_metrics": {
            "long_win_rate": round(profile.long_win_rate, 4),
            "short_win_rate": round(profile.short_win_rate, 4),
            "target_shrink_factor": round(profile.target_shrink_factor, 4),
            "mean_target_error": round(profile.mean_target_error, 4),
        },
    }

    prediction = PredictionRecord(
        prediction_id=f"{feature.ticker}:{feature.session_date.isoformat()}",
        ticker=feature.ticker,
        session_date=feature.session_date,
        direction=direction,
        entry_low=entry_low,
        entry_high=entry_high,
        stop_loss=stop_loss,
        confidence_score=round(confidence, 4),
        risk_reward=round(risk_reward, 4) if risk_reward is not None else None,
        holding_horizon_days=max(4, horizon),
        regime=feature.market_regime,
        reliability_label=reliability_label(profile.reliability_score, profile.insufficient_data),
        rationale=rationale,
        warning_flags=warning_flags,
        top_factors=sorted_factors[:4],
        profile_version=profile_version,
    )
    return prediction, targets


def evaluate_prediction(
    prediction: PredictionRecord,
    targets: list[TargetLevel],
    future_features: list[FeatureSnapshot],
) -> SignalOutcome:
    target_1 = next((item for item in targets if item.kind == "target_1"), None)
    target_2 = next((item for item in targets if item.kind == "target_2"), None)
    entry = prediction.entry_high if prediction.direction == "long" else prediction.entry_low

    if prediction.direction == "neutral" or entry is None or prediction.stop_loss is None or target_1 is None:
        return SignalOutcome(
            prediction_id=prediction.prediction_id,
            ticker=prediction.ticker,
            session_date=prediction.session_date,
            direction=prediction.direction,
            regime=prediction.regime,
            outcome_status="neutral",
            target_1_hit=False,
            target_2_hit=False,
            stop_hit=False,
            max_adverse_excursion=0.0,
            max_favorable_excursion=0.0,
            realized_return_pct=0.0,
            holding_days=0,
            target_error=0.0,
        )

    max_adverse = 0.0
    max_favorable = 0.0
    outcome_status = "timed_exit"
    target_1_hit = False
    target_2_hit = False
    stop_hit = False
    realized_return = 0.0
    holding_days = min(len(future_features), prediction.holding_horizon_days)

    for offset, feature in enumerate(future_features[: prediction.holding_horizon_days], start=1):
        if prediction.direction == "long":
            max_adverse = min(max_adverse, (feature.low - entry) / entry)
            max_favorable = max(max_favorable, (feature.high - entry) / entry)
            stop_reached = feature.low <= prediction.stop_loss
            target_1_reached = feature.high >= target_1.price
            target_2_reached = bool(target_2) and feature.high >= target_2.price
            if stop_reached:
                outcome_status = "stop"
                stop_hit = True
                realized_return = (prediction.stop_loss - entry) / entry
                holding_days = offset
                break
            if target_2_reached:
                outcome_status = "target_2"
                target_1_hit = True
                target_2_hit = True
                realized_return = (target_2.price - entry) / entry
                holding_days = offset
                break
            if target_1_reached and not target_1_hit:
                outcome_status = "target_1"
                target_1_hit = True
                realized_return = (target_1.price - entry) / entry
                holding_days = offset
                break
        else:
            max_adverse = min(max_adverse, (entry - feature.high) / entry)
            max_favorable = max(max_favorable, (entry - feature.low) / entry)
            stop_reached = feature.high >= prediction.stop_loss
            target_1_reached = feature.low <= target_1.price
            target_2_reached = bool(target_2) and feature.low <= target_2.price
            if stop_reached:
                outcome_status = "stop"
                stop_hit = True
                realized_return = (entry - prediction.stop_loss) / entry
                holding_days = offset
                break
            if target_2_reached:
                outcome_status = "target_2"
                target_1_hit = True
                target_2_hit = True
                realized_return = (entry - target_2.price) / entry
                holding_days = offset
                break
            if target_1_reached and not target_1_hit:
                outcome_status = "target_1"
                target_1_hit = True
                realized_return = (entry - target_1.price) / entry
                holding_days = offset
                break

    if outcome_status == "timed_exit" and future_features[: prediction.holding_horizon_days]:
        last_feature = future_features[min(len(future_features), prediction.holding_horizon_days) - 1]
        if prediction.direction == "long":
            realized_return = (last_feature.close - entry) / entry
            outcome_status = "open_gain" if realized_return > 0 else "open_loss"
        else:
            realized_return = (entry - last_feature.close) / entry
            outcome_status = "open_gain" if realized_return > 0 else "open_loss"

    predicted_move = abs(target_1.price - entry) / entry if entry else 0.0
    target_error = predicted_move - max_favorable
    return SignalOutcome(
        prediction_id=prediction.prediction_id,
        ticker=prediction.ticker,
        session_date=prediction.session_date,
        direction=prediction.direction,
        regime=prediction.regime,
        outcome_status=outcome_status,
        target_1_hit=target_1_hit,
        target_2_hit=target_2_hit,
        stop_hit=stop_hit,
        max_adverse_excursion=abs(max_adverse),
        max_favorable_excursion=max_favorable,
        realized_return_pct=realized_return,
        holding_days=holding_days,
        target_error=target_error,
    )
