from __future__ import annotations

from .calibration import clamp, reliability_label
from .models import FeatureSnapshot, PredictionRecord, ProfileSnapshot, SignalDirection, SignalOutcome, TargetLevel


def make_factor(name: str, contribution: float, detail: str) -> dict[str, float | str]:
    return {'name': name, 'contribution': round(contribution, 3), 'detail': detail}


def _direction_factors(feature: FeatureSnapshot) -> tuple[list[dict[str, float | str]], list[dict[str, float | str]]]:
    long_factors: list[dict[str, float | str]] = []
    short_factors: list[dict[str, float | str]] = []

    if feature.trend == 'UP':
        long_factors.append(make_factor('Trend', 2.0, 'Primary trend is up with price above the 50-day trend filter.'))
        short_factors.append(make_factor('Trend', -1.15, 'Primary trend does not support a fresh short.'))
    elif feature.trend == 'DOWN':
        short_factors.append(make_factor('Trend', 2.0, 'Primary trend is down with weak short-term structure.'))
        long_factors.append(make_factor('Trend', -1.15, 'Primary trend does not support a fresh long.'))
    else:
        long_factors.append(make_factor('Trend', -0.45, 'Trend structure is lateral.'))
        short_factors.append(make_factor('Trend', -0.45, 'Trend structure is lateral.'))

    if feature.breakout == 'bullish':
        long_factors.append(make_factor('Breakout', 1.3, 'Bullish breakout is confirmed on volume.'))
    elif feature.breakout == 'bearish':
        short_factors.append(make_factor('Breakout', 1.3, 'Bearish breakdown is confirmed on volume.'))

    if feature.market_regime == 'RISK_ON':
        long_factors.append(make_factor('Regime', 0.95, 'Risk-on backdrop supports continuation longs.'))
        short_factors.append(make_factor('Regime', -0.45, 'Risk-on backdrop reduces the quality of shorts.'))
    elif feature.market_regime == 'RISK_OFF':
        short_factors.append(make_factor('Regime', 0.95, 'Risk-off backdrop supports defensive shorts.'))
        long_factors.append(make_factor('Regime', -0.75, 'Risk-off backdrop penalizes fresh longs.'))
    else:
        long_factors.append(make_factor('Regime', 0.15, 'Regime adds only modest support.'))
        short_factors.append(make_factor('Regime', 0.15, 'Regime adds only modest support.'))

    if feature.adx >= 25:
        long_factors.append(make_factor('ADX', 0.7, 'Trend strength is above 25.'))
        short_factors.append(make_factor('ADX', 0.7, 'Trend strength is above 25.'))
    elif feature.adx < 18:
        long_factors.append(make_factor('ADX', -0.8, 'Trend strength is weak.'))
        short_factors.append(make_factor('ADX', -0.8, 'Trend strength is weak.'))

    if 52 <= feature.rsi <= 68:
        long_factors.append(make_factor('RSI', 0.6, 'Momentum is constructive without being overstretched.'))
    elif feature.rsi > 74:
        long_factors.append(make_factor('RSI', -0.7, 'Momentum is stretched for fresh longs.'))
        short_factors.append(make_factor('RSI', 0.25, 'Overbought condition helps the short thesis.'))

    if 32 <= feature.rsi <= 48:
        short_factors.append(make_factor('RSI', 0.6, 'Momentum is weak without being deeply oversold.'))
    elif feature.rsi < 26:
        short_factors.append(make_factor('RSI', -0.7, 'Momentum is stretched for fresh shorts.'))
        long_factors.append(make_factor('RSI', 0.25, 'Oversold condition may support a rebound.'))

    if feature.volume_ratio >= 1.15:
        long_factors.append(make_factor('Volume', 0.45, 'Participation is above the 20-day average.'))
        short_factors.append(make_factor('Volume', 0.45, 'Participation is above the 20-day average.'))
    elif feature.volume_ratio <= 0.85:
        long_factors.append(make_factor('Volume', -0.45, 'Participation is light.'))
        short_factors.append(make_factor('Volume', -0.45, 'Participation is light.'))

    if feature.relative_strength_1m > 0:
        long_factors.append(make_factor('Relative strength', 0.55, 'Ticker outperformed SPY over one month.'))
    else:
        short_factors.append(make_factor('Relative strength', 0.55, 'Ticker lagged SPY over one month.'))

    if feature.close_to_resistance_atr is not None and feature.close_to_resistance_atr < 0.7:
        long_factors.append(make_factor('Structure', -0.55, 'Price is close to nearby resistance.'))
    if feature.close_to_support_atr is not None and feature.close_to_support_atr < 0.7:
        short_factors.append(make_factor('Structure', -0.55, 'Price is close to nearby support.'))

    if abs(feature.close_vs_ema21_atr) > 1.6:
        if feature.close_vs_ema21_atr > 0:
            long_factors.append(make_factor('Extension', -0.6, 'Price is extended above EMA21 in ATR terms.'))
        else:
            short_factors.append(make_factor('Extension', -0.6, 'Price is extended below EMA21 in ATR terms.'))

    if abs(feature.gap_pct) >= 0.03:
        if feature.gap_pct > 0:
            long_factors.append(make_factor('Gap behaviour', -0.2, 'Large upside gap adds execution slippage risk.'))
        else:
            short_factors.append(make_factor('Gap behaviour', -0.2, 'Large downside gap adds execution slippage risk.'))

    return long_factors, short_factors


def _baseline_levels(feature: FeatureSnapshot, direction: SignalDirection, aggression: float) -> tuple[float | None, float | None, float | None, float | None, float | None, float | None]:
    if direction == 'neutral':
        return None, None, None, None, None, None

    atr = max(feature.atr, 0.01)
    regime_factor = 1.0
    if direction == 'long' and feature.market_regime == 'RISK_ON':
        regime_factor = 1.05
    elif direction == 'long' and feature.market_regime == 'RISK_OFF':
        regime_factor = 0.9
    elif direction == 'short' and feature.market_regime == 'RISK_OFF':
        regime_factor = 1.05
    elif direction == 'short' and feature.market_regime == 'RISK_ON':
        regime_factor = 0.9

    move_1 = atr * 1.45 * aggression * regime_factor
    move_2 = atr * 2.25 * aggression * regime_factor
    move_prob = atr * 1.05 * aggression

    entry_low = feature.close - (atr * 0.3) if direction == 'long' else feature.close
    entry_high = feature.close if direction == 'long' else feature.close + (atr * 0.3)

    if direction == 'long':
        structure_stop = feature.support if feature.support is not None else feature.close - (atr * 1.3)
        stop_loss = min(structure_stop, feature.close - (atr * 1.1))
        target_1 = feature.close + move_1
        target_2 = feature.close + move_2
        if feature.resistance is not None and feature.resistance > feature.close:
            target_1 = min(target_1, feature.resistance)
            target_2 = max(target_1, min(target_2, feature.resistance + atr))
        probabilistic_target = feature.close + move_prob
    else:
        structure_stop = feature.resistance if feature.resistance is not None else feature.close + (atr * 1.3)
        stop_loss = max(structure_stop, feature.close + (atr * 1.1))
        target_1 = feature.close - move_1
        target_2 = feature.close - move_2
        if feature.support is not None and feature.support < feature.close:
            target_1 = max(target_1, feature.support)
            target_2 = min(target_1, max(target_2, feature.support - atr))
        probabilistic_target = feature.close - move_prob

    return entry_low, entry_high, stop_loss, target_1, target_2, probabilistic_target


def _setup_name(feature: FeatureSnapshot, direction: SignalDirection) -> str:
    if direction == 'neutral':
        return 'stand-aside'
    if feature.breakout and direction != 'neutral':
        return 'breakout-continuation'
    if abs(feature.close_vs_ema21_atr) <= 0.8:
        return 'trend-pullback'
    return 'trend-continuation'


def _quality_bucket(confidence: float, warnings: list[str]) -> str:
    if confidence >= 0.76 and 'historical-overestimation' not in warnings:
        return 'high-conviction'
    if confidence <= 0.55 or 'insufficient-data' in warnings:
        return 'data-weak'
    return 'balanced'


def generate_prediction(feature: FeatureSnapshot, profile: ProfileSnapshot, *, profile_version: str, strategy_id: str = 'adaptive-swing-v2') -> tuple[PredictionRecord, list[TargetLevel]]:
    long_factors, short_factors = _direction_factors(feature)
    long_score = sum(float(item['contribution']) for item in long_factors)
    short_score = sum(float(item['contribution']) for item in short_factors)
    best_score = max(long_score, short_score)
    score_gap = abs(long_score - short_score)

    direction: SignalDirection = 'neutral'
    if best_score >= 2.15 and score_gap >= 0.75:
        direction = 'long' if long_score > short_score else 'short'

    structural_confidence = clamp(0.42 + (max(best_score, 0.0) / 8.2) * 0.35, 0.26, 0.86)
    confidence = clamp((0.56 * structural_confidence) + (0.44 * profile.reliability_score), 0.22, 0.94)
    if profile.insufficient_data:
        confidence = min(confidence, 0.62)
    if direction != 'neutral' and confidence < profile.confidence_floor:
        direction = 'neutral'

    warning_flags: list[str] = []
    entry_low = entry_high = stop_loss = target_1 = target_2 = probabilistic_target = None
    risk_reward = None
    targets: list[TargetLevel] = []
    aggression = profile.target_aggression * profile.target_shrink_factor

    if direction != 'neutral':
        entry_low, entry_high, stop_loss, target_1, target_2, probabilistic_target = _baseline_levels(feature, direction, aggression)
        if target_1 is not None and target_2 is not None and probabilistic_target is not None:
            distance_1 = abs(target_1 - feature.close)
            distance_2 = abs(target_2 - feature.close)
            distance_prob = abs(probabilistic_target - feature.close)
            calibrated_1 = distance_1 * profile.target_shrink_factor
            calibrated_2 = distance_2 * max(profile.target_shrink_factor, 0.85)
            calibrated_prob = distance_prob * max(profile.target_shrink_factor, 0.82)
            if direction == 'long':
                target_1 = feature.close + calibrated_1
                target_2 = feature.close + max(calibrated_2, calibrated_1 * 1.28)
                probabilistic_target = feature.close + calibrated_prob
            else:
                target_1 = feature.close - calibrated_1
                target_2 = feature.close - max(calibrated_2, calibrated_1 * 1.28)
                probabilistic_target = feature.close - calibrated_prob

        risk = abs(feature.close - stop_loss) if stop_loss is not None else None
        reward = abs(target_1 - feature.close) if target_1 is not None else None
        risk_reward = (reward / risk) if risk and reward else None

        if risk_reward is not None and risk_reward < 1.35:
            warning_flags.append('weak-risk-reward')
        if feature.volume_ratio < 0.85:
            warning_flags.append('low-volume')
        if abs(feature.close_vs_ema21_atr) > 1.6:
            warning_flags.append('overextended')
        if profile.target_shrink_factor < 0.92:
            warning_flags.append('historical-overestimation')
        if profile.insufficient_data:
            warning_flags.append('insufficient-data')
        if direction == 'long' and feature.market_regime == 'RISK_OFF':
            warning_flags.append('counter-regime-long')
        if direction == 'short' and feature.market_regime == 'RISK_ON':
            warning_flags.append('counter-regime-short')

        atr = max(feature.atr, 0.01)
        targets = [
            TargetLevel('target_1', round(target_1, 4), round(min(confidence + 0.06, 0.94), 4), round(abs(target_1 - feature.close) / atr, 4), 'Baseline target from ATR and structure, then calibrated by the ticker error profile.', 'signal_original', 1, feature.close),
            TargetLevel('target_2', round(target_2, 4), round(max(confidence - 0.08, 0.2), 4), round(abs(target_2 - feature.close) / atr, 4), 'Extended target kept only when regime and ticker profile justify follow-through.', 'signal_original', 1, feature.close),
            TargetLevel('probabilistic_target', round(probabilistic_target, 4), round(confidence, 4), round(abs(probabilistic_target - feature.close) / atr, 4), 'Mid-case objective for moderate extension scenarios.', 'signal_original', 1, feature.close),
        ]
    else:
        warning_flags.extend(['low-confidence', 'stand-aside'])
        if profile.insufficient_data:
            warning_flags.append('insufficient-data')

    factor_pool = short_factors if direction == 'short' else long_factors
    sorted_factors = sorted(factor_pool, key=lambda item: abs(float(item['contribution'])), reverse=True)
    horizon = 8 if feature.adx >= 25 else 11
    if profile.avg_days_to_target is not None:
        horizon = round((horizon + profile.avg_days_to_target) / 2)

    rationale = {
        'summary': 'Neutral posture because structure and ticker calibration do not show enough edge.' if direction == 'neutral' else f'{direction.title()} bias driven by structure, regime alignment, ATR framing, and ticker-specific calibration.',
        'target_reason': 'Targets combine ATR, support-resistance structure, and per-ticker model error correction.',
        'regime': feature.market_regime,
        'setup_name': _setup_name(feature, direction),
        'reliability': reliability_label(profile.reliability_score, profile.insufficient_data),
        'profile_metrics': {
            'long_win_rate': round(profile.long_win_rate, 4),
            'short_win_rate': round(profile.short_win_rate, 4),
            'setup_win_rate': round(profile.setup_win_rate, 4),
            'target_shrink_factor': round(profile.target_shrink_factor, 4),
            'confidence_calibration_error': round(profile.confidence_calibration_error, 4),
        },
    }

    prediction_id = f'signal-version:{feature.ticker}:{feature.session_date.isoformat()}:{strategy_id}'
    prediction = PredictionRecord(
        prediction_id=prediction_id,
        ticker=feature.ticker,
        session_date=feature.session_date,
        direction=direction,
        entry_low=round(entry_low, 4) if entry_low is not None else None,
        entry_high=round(entry_high, 4) if entry_high is not None else None,
        stop_loss=round(stop_loss, 4) if stop_loss is not None else None,
        confidence_score=round(confidence, 4),
        risk_reward=round(risk_reward, 4) if risk_reward is not None else None,
        holding_horizon_days=max(4, horizon),
        regime=feature.market_regime,
        reliability_label=reliability_label(profile.reliability_score, profile.insufficient_data),
        rationale=rationale,
        warning_flags=warning_flags,
        top_factors=sorted_factors[:5],
        profile_version=profile_version,
        strategy_id=strategy_id,
        signal_id=f'signal:{feature.ticker}:{strategy_id}',
        generated_at=f'{feature.session_date.isoformat()}T21:00:00Z',
        setup_name=_setup_name(feature, direction),
        setup_quality=_quality_bucket(confidence, warning_flags),
    )
    return prediction, targets


def evaluate_prediction(prediction: PredictionRecord, targets: list[TargetLevel], future_features: list[FeatureSnapshot]) -> SignalOutcome:
    target_1 = next((item for item in targets if item.kind == 'target_1'), None)
    target_2 = next((item for item in targets if item.kind == 'target_2'), None)
    entry = prediction.entry_high if prediction.direction == 'long' else prediction.entry_low

    if prediction.direction == 'neutral' or entry is None or prediction.stop_loss is None or target_1 is None:
        return SignalOutcome(
            prediction_id=prediction.prediction_id,
            ticker=prediction.ticker,
            session_date=prediction.session_date,
            direction=prediction.direction,
            regime=prediction.regime,
            outcome_status='neutral',
            target_1_hit=False,
            target_2_hit=False,
            stop_hit=False,
            max_adverse_excursion=0.0,
            max_favorable_excursion=0.0,
            realized_return_pct=0.0,
            holding_days=0,
            target_error=0.0,
            prediction_confidence=prediction.confidence_score,
            setup_name=prediction.setup_name,
            signal_history_id=f'signal-history:{prediction.prediction_id}',
            signal_version_id=prediction.prediction_id,
            signal_id=prediction.signal_id or prediction.prediction_id,
        )

    max_adverse = 0.0
    max_favorable = 0.0
    outcome_status = 'timed_exit'
    target_1_hit = False
    target_2_hit = False
    stop_hit = False
    realized_return = 0.0
    holding_days = min(len(future_features), prediction.holding_horizon_days)

    for offset, feature in enumerate(future_features[: prediction.holding_horizon_days], start=1):
        if prediction.direction == 'long':
            max_adverse = min(max_adverse, (feature.low - entry) / entry)
            max_favorable = max(max_favorable, (feature.high - entry) / entry)
            if feature.low <= prediction.stop_loss:
                outcome_status = 'stop'
                stop_hit = True
                realized_return = (prediction.stop_loss - entry) / entry
                holding_days = offset
                break
            if target_2 is not None and feature.high >= target_2.price:
                outcome_status = 'target_2'
                target_1_hit = True
                target_2_hit = True
                realized_return = (target_2.price - entry) / entry
                holding_days = offset
                break
            if feature.high >= target_1.price:
                outcome_status = 'target_1'
                target_1_hit = True
                realized_return = (target_1.price - entry) / entry
                holding_days = offset
                break
        else:
            max_adverse = min(max_adverse, (entry - feature.high) / entry)
            max_favorable = max(max_favorable, (entry - feature.low) / entry)
            if feature.high >= prediction.stop_loss:
                outcome_status = 'stop'
                stop_hit = True
                realized_return = (entry - prediction.stop_loss) / entry
                holding_days = offset
                break
            if target_2 is not None and feature.low <= target_2.price:
                outcome_status = 'target_2'
                target_1_hit = True
                target_2_hit = True
                realized_return = (entry - target_2.price) / entry
                holding_days = offset
                break
            if feature.low <= target_1.price:
                outcome_status = 'target_1'
                target_1_hit = True
                realized_return = (entry - target_1.price) / entry
                holding_days = offset
                break

    if outcome_status == 'timed_exit' and future_features[: prediction.holding_horizon_days]:
        last_feature = future_features[min(len(future_features), prediction.holding_horizon_days) - 1]
        if prediction.direction == 'long':
            realized_return = (last_feature.close - entry) / entry
            outcome_status = 'open_gain' if realized_return > 0 else 'open_loss'
        else:
            realized_return = (entry - last_feature.close) / entry
            outcome_status = 'open_gain' if realized_return > 0 else 'open_loss'

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
        prediction_confidence=prediction.confidence_score,
        setup_name=prediction.setup_name,
        signal_history_id=f'signal-history:{prediction.prediction_id}',
        signal_version_id=prediction.prediction_id,
        signal_id=prediction.signal_id or prediction.prediction_id,
    )
