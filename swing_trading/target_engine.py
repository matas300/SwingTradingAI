from __future__ import annotations

from .calibration import clamp
from .models import FeatureSnapshot, PositionState, PredictionRecord, ProfileSnapshot, TargetLevel, TargetSetRecord


def _find_target(targets: list[TargetLevel], kind: str) -> float | None:
    target = next((item for item in targets if item.kind == kind), None)
    return target.price if target else None


def signal_target_set(prediction: PredictionRecord, targets: list[TargetLevel]) -> TargetSetRecord:
    entry_reference = prediction.entry_high if prediction.direction == "long" else prediction.entry_low
    return TargetSetRecord(
        target_id=f"targets:signal:{prediction.signal_id}",
        owner_type="signal",
        owner_id=prediction.signal_id,
        scope="signal_original",
        side=prediction.direction,
        reference_entry_price=entry_reference,
        average_entry_price=entry_reference,
        stop_loss=prediction.stop_loss,
        target_1=_find_target(targets, "target_1"),
        target_2=_find_target(targets, "target_2"),
        optional_target_3=_find_target(targets, "target_3"),
        probabilistic_target=_find_target(targets, "probabilistic_target"),
        risk_reward=prediction.risk_reward,
        confidence_score=prediction.confidence_score,
        holding_horizon_days=prediction.holding_horizon_days,
        rationale=prediction.rationale,
        warning_flags=prediction.warning_flags,
        generated_at=prediction.generated_at,
        version_tag=prediction.profile_version,
        ticker_symbol=prediction.ticker,
    )


def adaptive_position_targets(
    *,
    position: PositionState,
    signal: PredictionRecord,
    profile: ProfileSnapshot,
    market_snapshot: FeatureSnapshot,
    original_targets: TargetSetRecord | None,
) -> TargetSetRecord:
    original_entry = (
        original_targets.reference_entry_price
        if original_targets and original_targets.reference_entry_price is not None
        else signal.entry_reference_price
    )
    anchor_entry = position.average_entry_price or position.initial_entry_price or original_entry or market_snapshot.close
    base_t1_distance = abs((original_targets.target_1 if original_targets else market_snapshot.close) - (original_entry or market_snapshot.close))
    base_t2_distance = abs((original_targets.target_2 if original_targets else market_snapshot.close) - (original_entry or market_snapshot.close))
    base_prob_distance = abs((original_targets.probabilistic_target if original_targets else market_snapshot.close) - (original_entry or market_snapshot.close))
    atr = max(market_snapshot.atr, 0.01)
    calibration = clamp((profile.target_shrink_factor * 0.65) + (profile.target_aggression * 0.35), 0.74, 1.18)
    regime_factor = 1.0
    if market_snapshot.market_regime == "RISK_OFF" and position.side == "long":
        regime_factor = 0.92
    elif market_snapshot.market_regime == "RISK_ON" and position.side == "short":
        regime_factor = 0.92
    elif market_snapshot.market_regime == "RISK_ON" and position.side == "long":
        regime_factor = 1.05
    elif market_snapshot.market_regime == "RISK_OFF" and position.side == "short":
        regime_factor = 1.05

    distance_1 = max(base_t1_distance * calibration * regime_factor, atr * 0.9)
    distance_2 = max(base_t2_distance * calibration * regime_factor, distance_1 * 1.3, atr * 1.6)
    distance_prob = max(base_prob_distance * calibration, distance_1 * 1.1, atr * 0.8)

    if position.side == "long":
        target_1 = anchor_entry + distance_1
        target_2 = anchor_entry + distance_2
        probabilistic_target = anchor_entry + distance_prob
        stop_floor = original_targets.stop_loss if original_targets and original_targets.stop_loss is not None else anchor_entry - (atr * 1.25)
        structure_stop = market_snapshot.support if market_snapshot.support is not None else anchor_entry - (atr * 1.2)
        stop_loss = max(min(stop_floor, anchor_entry - (atr * 0.55)), structure_stop - (atr * 0.15))
    else:
        target_1 = anchor_entry - distance_1
        target_2 = anchor_entry - distance_2
        probabilistic_target = anchor_entry - distance_prob
        stop_ceiling = original_targets.stop_loss if original_targets and original_targets.stop_loss is not None else anchor_entry + (atr * 1.25)
        structure_stop = market_snapshot.resistance if market_snapshot.resistance is not None else anchor_entry + (atr * 1.2)
        stop_loss = min(max(stop_ceiling, anchor_entry + (atr * 0.55)), structure_stop + (atr * 0.15))

    risk = abs(anchor_entry - stop_loss) if stop_loss is not None else None
    reward = abs(target_1 - anchor_entry) if target_1 is not None else None
    risk_reward = (reward / risk) if risk and reward else None
    rationale = {
        "summary": "Adaptive targets preserve the original signal geometry while re-anchoring to the real average entry.",
        "original_entry_reference": original_entry,
        "average_entry_reference": anchor_entry,
        "calibration_factor": round(calibration, 4),
        "regime_factor": round(regime_factor, 4),
        "profile_target_shrink_factor": round(profile.target_shrink_factor, 4),
    }
    warning_flags = list(dict.fromkeys((original_targets.warning_flags if original_targets else []) + signal.warning_flags))
    if profile.target_shrink_factor < 0.9:
        warning_flags.append("adaptive-targets-derated")

    return TargetSetRecord(
        target_id=f"targets:position:{position.position_id}",
        owner_type="position",
        owner_id=position.position_id,
        scope="position_adaptive",
        side=position.side,
        reference_entry_price=position.initial_entry_price or original_entry,
        average_entry_price=anchor_entry,
        stop_loss=round(stop_loss, 4) if stop_loss is not None else None,
        target_1=round(target_1, 4) if target_1 is not None else None,
        target_2=round(target_2, 4) if target_2 is not None else None,
        optional_target_3=None,
        probabilistic_target=round(probabilistic_target, 4) if probabilistic_target is not None else None,
        risk_reward=round(risk_reward, 4) if risk_reward is not None else None,
        confidence_score=signal.confidence_score,
        holding_horizon_days=signal.holding_horizon_days,
        rationale=rationale,
        warning_flags=warning_flags,
        generated_at=signal.generated_at,
        version_tag=f"adaptive:{market_snapshot.session_date.isoformat()}",
        ticker_symbol=position.ticker,
    )
