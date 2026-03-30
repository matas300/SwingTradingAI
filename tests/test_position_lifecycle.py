from datetime import datetime

import pytest

from swing_trading.models import PositionEvent, TargetLevel
from swing_trading.position_lifecycle import distance_to_level_pct, pnl_for_close, rebuild_position_summary


def make_level(kind: str, price: float, *, scope: str = "original") -> TargetLevel:
    return TargetLevel(
        kind=kind,
        price=price,
        probability=0.7,
        distance_atr=1.0,
        rationale=f"{kind} for test",
        scope=scope,
        version=1,
        reference_price=100.0,
    )


def make_event(event_id: str, event_type: str, quantity: float, price: float, executed_at: datetime) -> PositionEvent:
    return PositionEvent(
        event_id=event_id,
        position_id="position:test",
        user_id="user:test",
        ticker="AAPL",
        side="long",
        event_type=event_type,
        quantity=quantity,
        price=price,
        fees=0.0,
        executed_at=executed_at,
        source="user",
        linked_signal_id="signal:test",
        metadata={},
        notes="",
        created_at=executed_at.isoformat(),
    )


def test_pnl_for_close_is_signed_by_side():
    assert pnl_for_close("long", 100.0, 112.0, 3.0) == pytest.approx(36.0)
    assert pnl_for_close("short", 100.0, 88.0, 3.0) == pytest.approx(36.0)


def test_distance_to_level_pct_uses_directional_distance():
    assert distance_to_level_pct(side="long", current_price=110.0, level=121.0, intent="target") == pytest.approx(0.1)
    assert distance_to_level_pct(side="long", current_price=110.0, level=98.0, intent="stop") == pytest.approx(0.1090909091)
    assert distance_to_level_pct(side="short", current_price=90.0, level=79.0, intent="target") == pytest.approx(0.1222222222)
    assert distance_to_level_pct(side="short", current_price=90.0, level=96.0, intent="stop") == pytest.approx(0.0666666667)


def test_rebuild_position_summary_handles_partial_add_and_reduce():
    opened_at = datetime(2026, 3, 24, 10, 0, 0)
    mark_price = 110.0
    events = [
        make_event("event-open", "OPEN", 10.0, 100.0, opened_at),
        make_event("event-add", "ADD", 10.0, 110.0, opened_at.replace(hour=11)),
        make_event("event-reduce", "REDUCE", 8.0, 120.0, opened_at.replace(hour=12)),
    ]

    summary = rebuild_position_summary(
        position_id="position:test",
        user_id="user:test",
        ticker="AAPL",
        strategy_id="adaptive-swing-v2",
        signal_id_origin="signal:test",
        side="long",
        opened_at=opened_at,
        events=events,
        original_targets=[make_level("target_1", 115.0), make_level("target_2", 125.0), make_level("target_3", 130.0)],
        adaptive_targets=[make_level("target_1", 115.0, scope="adaptive"), make_level("target_2", 125.0, scope="adaptive"), make_level("target_3", 130.0, scope="adaptive")],
        original_stop=95.0,
        current_stop=97.7,
        mark_price=mark_price,
        as_of=datetime(2026, 3, 25, 16, 0, 0),
        price_history=[
            {"high": 123.0, "low": 97.0, "close": 110.0},
            {"high": 121.0, "low": 101.0, "close": 108.0},
        ],
        last_recommendation="maintain",
        last_recommendation_confidence=0.71,
        last_recommendation_reason="Trend intact.",
        base_notes="",
    )

    assert summary.status == "open"
    assert summary.initial_entry_price == pytest.approx(100.0)
    assert summary.average_entry_price == pytest.approx(105.0)
    assert summary.initial_quantity == pytest.approx(10.0)
    assert summary.current_quantity == pytest.approx(12.0)
    assert summary.realized_pnl == pytest.approx(120.0)
    assert summary.unrealized_pnl == pytest.approx(60.0)
    assert summary.total_pnl == pytest.approx(180.0)
    assert summary.gross_exposure == pytest.approx(1320.0)
    assert summary.distance_to_stop_pct == pytest.approx((110.0 - 97.7) / 110.0)
    assert summary.distance_to_target_1_pct == pytest.approx((115.0 - 110.0) / 110.0)
    assert summary.distance_to_target_2_pct == pytest.approx((125.0 - 110.0) / 110.0)
    assert summary.max_favorable_excursion == pytest.approx(0.23)
    assert summary.max_adverse_excursion == pytest.approx(0.03)


def test_rebuild_position_summary_closes_position_and_tracks_realized_pnl():
    opened_at = datetime(2026, 3, 24, 10, 0, 0)
    close_time = opened_at.replace(hour=15)
    events = [
        make_event("event-open", "OPEN", 5.0, 50.0, opened_at),
        make_event("event-close", "CLOSE", 5.0, 54.0, close_time),
    ]

    summary = rebuild_position_summary(
        position_id="position:test-close",
        user_id="user:test",
        ticker="MSFT",
        strategy_id="adaptive-swing-v2",
        signal_id_origin="signal:test-close",
        side="long",
        opened_at=opened_at,
        events=events,
        original_targets=[make_level("target_1", 56.0), make_level("target_2", 60.0)],
        adaptive_targets=[make_level("target_1", 56.0, scope="adaptive"), make_level("target_2", 60.0, scope="adaptive")],
        original_stop=47.0,
        current_stop=47.5,
        mark_price=54.0,
        as_of=datetime(2026, 3, 25, 16, 0, 0),
        price_history=[{"high": 55.0, "low": 49.0, "close": 52.0}],
        last_recommendation="close",
        last_recommendation_confidence=0.86,
        last_recommendation_reason="Stop was hit.",
        base_notes="",
    )

    assert summary.status == "closed"
    assert summary.current_quantity == pytest.approx(0.0)
    assert summary.closed_at == close_time
    assert summary.realized_pnl == pytest.approx(20.0)
    assert summary.unrealized_pnl == pytest.approx(0.0)
    assert summary.total_pnl == pytest.approx(20.0)
