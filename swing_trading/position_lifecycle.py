from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from .models import PositionEvent, PositionSummary, PositionSide, TargetLevel


def pnl_for_close(side: PositionSide, entry_price: float, exit_price: float, quantity: float) -> float:
    return (exit_price - entry_price) * quantity if side == "long" else (entry_price - exit_price) * quantity


def distance_to_level_pct(
    *,
    side: PositionSide,
    current_price: float | None,
    level: float | None,
    intent: str,
) -> float | None:
    if current_price is None or level is None or current_price <= 0:
        return None
    if intent == "stop":
        if side == "long":
            return max((current_price - level) / current_price, 0.0)
        return max((level - current_price) / current_price, 0.0)
    if side == "long":
        return max((level - current_price) / current_price, 0.0)
    return max((current_price - level) / current_price, 0.0)


def extract_target_price(targets: list[TargetLevel], kind: str) -> float | None:
    match = next((target for target in targets if target.kind == kind), None)
    return match.price if match else None


def serialize_targets(targets: list[TargetLevel], scope: str) -> list[TargetLevel]:
    return [replace(target, scope=scope) for target in targets]


def _coerce_targets(payload: Any, fallback_scope: str) -> list[TargetLevel]:
    if not payload:
        return []
    if isinstance(payload[0], TargetLevel):
        return [replace(item, scope=item.scope or fallback_scope) for item in payload]
    targets: list[TargetLevel] = []
    for item in payload:
        targets.append(
            TargetLevel(
                kind=str(item.get("kind")),
                price=float(item.get("price", 0.0)),
                probability=float(item["probability"]) if item.get("probability") is not None else None,
                distance_atr=float(item.get("distance_atr", 0.0)),
                rationale=str(item.get("rationale", "")),
                scope=str(item.get("scope", fallback_scope)),
                version=int(item.get("version", 1)),
                reference_price=float(item["reference_price"]) if item.get("reference_price") is not None else None,
            )
        )
    return targets


def compute_excursions(
    side: PositionSide,
    reference_entry: float,
    price_history: list[dict[str, Any]] | None,
) -> tuple[float, float]:
    if not price_history or reference_entry <= 0:
        return 0.0, 0.0

    favorable = 0.0
    adverse = 0.0
    for point in price_history:
        high = float(point.get("high", point.get("close", reference_entry)))
        low = float(point.get("low", point.get("close", reference_entry)))
        if side == "long":
            favorable = max(favorable, (high - reference_entry) / reference_entry)
            adverse = max(adverse, (reference_entry - low) / reference_entry)
        else:
            favorable = max(favorable, (reference_entry - low) / reference_entry)
            adverse = max(adverse, (high - reference_entry) / reference_entry)
    return favorable, adverse


def rebuild_position_summary(
    *,
    position_id: str,
    user_id: str,
    ticker: str,
    strategy_id: str,
    signal_id_origin: str,
    side: PositionSide,
    opened_at: datetime,
    events: list[PositionEvent],
    original_targets: list[TargetLevel] | list[dict[str, Any]],
    adaptive_targets: list[TargetLevel] | list[dict[str, Any]],
    original_stop: float | None,
    current_stop: float | None,
    mark_price: float | None,
    as_of: datetime,
    price_history: list[dict[str, Any]] | None = None,
    last_recommendation: str | None = None,
    last_recommendation_confidence: float | None = None,
    last_recommendation_reason: str | None = None,
    base_notes: str = "",
) -> PositionSummary:
    sorted_events = sorted(events, key=lambda item: (item.executed_at, item.event_id))
    original_targets_typed = serialize_targets(_coerce_targets(original_targets, "original"), "original")
    adaptive_targets_typed = serialize_targets(_coerce_targets(adaptive_targets, "adaptive"), "adaptive")
    active_stop = current_stop if current_stop is not None else original_stop
    current_quantity = 0.0
    cost_basis = 0.0
    realized_pnl = 0.0
    initial_entry_price = 0.0
    average_entry_price = 0.0
    initial_quantity = 0.0
    latest_notes = base_notes.strip()
    closed_at: datetime | None = None

    for event in sorted_events:
        if event.event_type in {"OPEN", "ADD"}:
            trade_price = float(event.price or 0.0)
            cost_basis += trade_price * event.quantity
            current_quantity += event.quantity
            average_entry_price = cost_basis / current_quantity if current_quantity > 0 else average_entry_price
            if event.event_type == "OPEN" and initial_quantity == 0.0:
                initial_quantity = event.quantity
                initial_entry_price = trade_price
        elif event.event_type in {"REDUCE", "CLOSE"}:
            if current_quantity <= 0:
                continue
            exit_quantity = current_quantity if event.event_type == "CLOSE" else min(event.quantity, current_quantity)
            realized_pnl += pnl_for_close(side, average_entry_price, float(event.price or 0.0), exit_quantity) - float(event.fees)
            current_quantity = max(current_quantity - exit_quantity, 0.0)
            cost_basis = average_entry_price * current_quantity
            if current_quantity == 0:
                closed_at = event.executed_at
        elif event.event_type == "UPDATE_STOP":
            override = event.metadata.get("stop", event.price)
            active_stop = float(override) if override is not None else active_stop
        elif event.event_type == "UPDATE_TARGETS":
            payload = event.metadata.get("targets")
            if payload:
                adaptive_targets_typed = serialize_targets(_coerce_targets(payload, "adaptive"), "adaptive")
        if event.notes:
            latest_notes = "\n".join(filter(None, [latest_notes, event.notes.strip()])).strip()

    if initial_quantity == 0.0 and sorted_events:
        opening_event = sorted_events[0]
        initial_quantity = opening_event.quantity
        initial_entry_price = float(opening_event.price or 0.0)
    if average_entry_price == 0.0:
        average_entry_price = initial_entry_price

    current_mark = mark_price if mark_price is not None else average_entry_price
    unrealized_pnl = pnl_for_close(side, average_entry_price, current_mark, current_quantity) if current_quantity > 0 else 0.0
    total_pnl = realized_pnl + unrealized_pnl
    gross_exposure = abs(current_quantity * (current_mark or average_entry_price))
    holding_days = max((as_of.date() - opened_at.date()).days, 0)
    mfe, mae = compute_excursions(side, initial_entry_price or average_entry_price, price_history)
    effective_targets = adaptive_targets_typed or original_targets_typed

    return PositionSummary(
        position_id=position_id,
        user_id=user_id,
        ticker=ticker,
        strategy_id=strategy_id,
        signal_id_origin=signal_id_origin,
        side=side,
        status="open" if current_quantity > 0 else "closed",
        initial_entry_price=round(initial_entry_price, 4),
        average_entry_price=round(average_entry_price, 4),
        initial_quantity=round(initial_quantity, 4),
        current_quantity=round(current_quantity, 4),
        opened_at=opened_at,
        closed_at=closed_at,
        current_stop=round(active_stop, 4) if active_stop is not None else None,
        original_stop=round(original_stop, 4) if original_stop is not None else None,
        targets_from_original_signal=original_targets_typed,
        current_adaptive_targets=effective_targets,
        realized_pnl=round(realized_pnl, 4),
        unrealized_pnl=round(unrealized_pnl, 4),
        total_pnl=round(total_pnl, 4),
        gross_exposure=round(gross_exposure, 4),
        holding_days=holding_days,
        max_favorable_excursion=round(mfe, 4),
        max_adverse_excursion=round(mae, 4),
        distance_to_stop_pct=distance_to_level_pct(side=side, current_price=current_mark, level=active_stop, intent="stop"),
        distance_to_target_1_pct=distance_to_level_pct(
            side=side,
            current_price=current_mark,
            level=extract_target_price(effective_targets, "target_1"),
            intent="target",
        ),
        distance_to_target_2_pct=distance_to_level_pct(
            side=side,
            current_price=current_mark,
            level=extract_target_price(effective_targets, "target_2"),
            intent="target",
        ),
        mark_price=round(current_mark, 4) if current_mark is not None else None,
        last_recommendation=last_recommendation,
        last_recommendation_confidence=last_recommendation_confidence,
        last_recommendation_reason=last_recommendation_reason,
        warning_flags=[],
        notes=latest_notes,
    )


def calculate_position_state(
    *,
    position_id: str,
    user_id: str,
    ticker: str,
    side: PositionSide,
    signal_id_origin: str | None,
    strategy_id: str | None,
    strategy_name: str | None = None,
    events: list[PositionEvent],
    last_price: float | None,
    price_history: list[dict[str, Any]] | None,
    as_of_date: date,
    last_recommendation: str | None,
    last_recommendation_confidence: float | None,
    notes: str | None = None,
) -> PositionSummary:
    opening_event = next((event for event in events if event.event_type == "OPEN"), events[0] if events else None)
    if opening_event is None:
        raise ValueError(f"Position {position_id} has no events to rebuild state.")
    original_stop = opening_event.metadata.get("stop")
    original_targets = opening_event.metadata.get("targets", [])
    adaptive_targets = original_targets
    for event in events:
        if event.event_type == "UPDATE_TARGETS" and event.metadata.get("targets"):
            adaptive_targets = event.metadata.get("targets")
    return rebuild_position_summary(
        position_id=position_id,
        user_id=user_id,
        ticker=ticker,
        strategy_id=strategy_id or strategy_name or "adaptive-swing-v2",
        signal_id_origin=signal_id_origin or "",
        side=side,
        opened_at=opening_event.executed_at,
        events=events,
        original_targets=original_targets,
        adaptive_targets=adaptive_targets,
        original_stop=float(original_stop) if original_stop is not None else None,
        current_stop=None,
        mark_price=last_price,
        as_of=datetime.combine(as_of_date, datetime.min.time()),
        price_history=price_history,
        last_recommendation=last_recommendation,
        last_recommendation_confidence=last_recommendation_confidence,
        last_recommendation_reason=None,
        base_notes=notes or "",
    )
