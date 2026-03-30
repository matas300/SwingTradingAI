from __future__ import annotations

from .calibration import clamp
from .models import (
    FeatureSnapshot,
    PositionRecommendation,
    PositionState,
    PredictionRecord,
    ProfileSnapshot,
    TargetSetRecord,
)


def recommend_position_action(
    *,
    position: PositionState,
    signal: PredictionRecord,
    profile: ProfileSnapshot,
    market_snapshot: FeatureSnapshot,
    original_targets: TargetSetRecord | None,
    adaptive_targets: TargetSetRecord | None,
    effective_at: str,
) -> PositionRecommendation:
    current_targets = adaptive_targets or original_targets
    target_1 = current_targets.target_1 if current_targets else None
    target_2 = current_targets.target_2 if current_targets else None
    stop_loss = current_targets.stop_loss if current_targets and current_targets.stop_loss is not None else original_targets.stop_loss if original_targets else signal.stop_loss

    signal_alignment = signal.direction == position.side
    close_to_stop = (position.distance_to_stop_pct or 1.0) <= 0.015
    near_target = (position.distance_to_target_1_pct or 1.0) <= 0.02
    extension = abs(market_snapshot.close_vs_ema21_atr) >= 1.35
    low_trend_quality = market_snapshot.adx < 18
    risk_loaded = position.current_quantity >= position.initial_quantity * 1.5
    profile_weak = profile.insufficient_data or profile.reliability_score < 0.48
    pnl_positive = position.total_pnl > 0
    rsi_stretched = (position.side == "long" and market_snapshot.rsi >= 70) or (position.side == "short" and market_snapshot.rsi <= 30)
    warning_flags = list(dict.fromkeys((original_targets.warning_flags if original_targets else []) + (adaptive_targets.warning_flags if adaptive_targets else []) + signal.warning_flags))
    confidence = clamp(
        signal.confidence_score * 0.55 + profile.reliability_score * 0.30 + (1.0 - min(profile.mean_target_error, 0.4)) * 0.15,
        0.2,
        0.92,
    )
    reasons: list[str] = []
    action = "maintain"
    add_qty: float | None = None
    reduce_qty: float | None = None
    zone_low: float | None = None
    zone_high: float | None = None

    if close_to_stop:
        action = "close"
        reasons.append("price is too close to the active stop")
        warning_flags.append("stop-proximity")
    elif signal.direction == "neutral":
        action = "reduce" if pnl_positive else "close"
        reasons.append("latest study signal lost directional edge")
    elif not signal_alignment:
        action = "close" if confidence < 0.64 else "reduce"
        reasons.append("validated signal flipped against the live position")
        warning_flags.append("signal-flip")
    elif near_target and (extension or pnl_positive):
        action = "reduce"
        reasons.append("target 1 is close and upside extension is fading")
    elif low_trend_quality and extension:
        action = "reduce"
        reasons.append("trend strength is fading while price remains extended")
    elif signal_alignment and signal.confidence_score >= 0.7 and not risk_loaded and not profile_weak and not extension and (position.distance_to_stop_pct or 0.0) >= 0.04:
        action = "add"
        reasons.append("signal remains aligned with acceptable room to stop")
        reasons.append("total size is still below the defined risk envelope")
    elif profile_weak:
        action = "no_action"
        reasons.append("ticker profile quality is not strong enough for a size change")
        warning_flags.append("data-weak")
    else:
        reasons.append("trend, targets, and size remain broadly aligned")

    if rsi_stretched and action == "add":
        action = "maintain"
        reasons = ["momentum is too stretched for a disciplined add"]
        warning_flags.append("stretched-momentum")

    if action == "add":
        add_qty = round(max(position.initial_quantity * 0.25, 1.0), 4)
        anchor = signal.entry_reference_price or market_snapshot.close
        zone_low = round(anchor - market_snapshot.atr * 0.15, 4)
        zone_high = round(anchor + market_snapshot.atr * 0.1, 4)
    elif action == "reduce":
        reduce_qty = round(max(position.current_quantity * 0.25, 1.0), 4)
    elif action == "close":
        reduce_qty = round(position.current_quantity, 4)

    return PositionRecommendation(
        recommendation_id=f"rec:{position.position_id}:{effective_at[:10]}",
        position_id=position.position_id,
        user_id=position.user_id,
        effective_at=effective_at,
        action=action,  # type: ignore[arg-type]
        confidence=round(confidence, 4),
        rationale="Reason: " + "; ".join(reasons),
        warning_flags=list(dict.fromkeys(warning_flags)),
        suggested_add_qty=add_qty,
        suggested_reduce_qty=reduce_qty,
        suggested_stop=round(stop_loss, 4) if stop_loss is not None else None,
        suggested_target_1=round(target_1, 4) if target_1 is not None else None,
        suggested_target_2=round(target_2, 4) if target_2 is not None else None,
        suggested_target_3=round(current_targets.target_3, 4) if current_targets and current_targets.target_3 is not None else None,
        suggested_zone_low=zone_low,
        suggested_zone_high=zone_high,
        suggested_size_action=(
            f"add {add_qty:g}"
            if add_qty is not None
            else f"reduce {reduce_qty:g}"
            if action == "reduce" and reduce_qty is not None
            else "close all"
            if action == "close"
            else "hold"
        ),
    )
