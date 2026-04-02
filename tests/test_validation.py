import pytest
from datetime import datetime, timezone
from swing_trading.validation import (
    normalize_ticker,
    normalize_ticker_list,
    ensure_positive_number,
    ensure_non_negative_number,
    normalize_timestamp,
)

def test_normalize_ticker():
    # Happy paths
    assert normalize_ticker("AAPL") == "AAPL"
    assert normalize_ticker(" aapl ") == "AAPL"
    assert normalize_ticker("BRK-A") == "BRK-A"
    assert normalize_ticker("BRK.A") == "BRK.A"

    # Invalid tickers
    with pytest.raises(ValueError, match="Invalid ticker"):
        normalize_ticker("")
    with pytest.raises(ValueError, match="Invalid ticker"):
        normalize_ticker("   ")
    with pytest.raises(ValueError, match="Invalid ticker"):
        normalize_ticker("A" * 15)
    with pytest.raises(ValueError, match="Invalid ticker"):
        normalize_ticker("-AAPL")
    with pytest.raises(ValueError, match="Invalid ticker"):
        normalize_ticker(".AAPL")

def test_normalize_ticker_list():
    # Empty list
    assert normalize_ticker_list([]) == []

    # Normal list
    assert normalize_ticker_list(["AAPL", "GOOGL"]) == ["AAPL", "GOOGL"]

    # Duplicates and casing
    assert normalize_ticker_list(["AAPL", "aapl", "GOOGL ", " aapl", "MSFT"]) == ["AAPL", "GOOGL", "MSFT"]

    # Invalid elements
    with pytest.raises(ValueError, match="Invalid ticker"):
        normalize_ticker_list(["AAPL", ""])

def test_ensure_positive_number():
    assert ensure_positive_number(10.5, "price") == 10.5
    assert ensure_positive_number("5.0", "price") == 5.0

    with pytest.raises(ValueError, match="price must be greater than zero"):
        ensure_positive_number(0, "price")
    with pytest.raises(ValueError, match="price must be greater than zero"):
        ensure_positive_number(-5.5, "price")

def test_ensure_non_negative_number():
    assert ensure_non_negative_number(10.5, "volume") == 10.5
    assert ensure_non_negative_number("5.0", "volume") == 5.0
    assert ensure_non_negative_number(0, "volume") == 0.0
    assert ensure_non_negative_number(None, "volume") == 0.0

    with pytest.raises(ValueError, match="volume cannot be negative"):
        ensure_non_negative_number(-5.5, "volume")

def test_ensure_non_negative_number_edge_cases():
    assert ensure_non_negative_number(5.0, "Test Field") == 5.0
    assert ensure_non_negative_number(0.0, "Test Field") == 0.0
    assert ensure_non_negative_number(None, "Test Field") == 0.0
    with pytest.raises(ValueError, match="Test Field cannot be negative."):
        ensure_non_negative_number(-1.0, "Test Field")

def test_normalize_timestamp():
    # Empty timestamp gets current UTC
    now_ts = normalize_timestamp(None)
    assert now_ts.endswith("Z")

    # 'Z' suffixed timestamps
    ts = normalize_timestamp("2023-01-01T12:00:00Z")
    assert "2023-01-01T12:00:00" in ts

    # Offset timestamps
    ts2 = normalize_timestamp("2023-01-01T12:00:00+00:00")
    assert "2023-01-01T12:00:00" in ts2

    # Local time without timezone gets converted as if it was already local/UTC based on system
    assert normalize_timestamp("2023-01-01T12:00:00") == "2023-01-01T12:00:00Z"

def test_normalize_timestamp_none_or_empty():
    # Test None
    res = normalize_timestamp(None)
    assert res.endswith("Z")
    assert datetime.fromisoformat(res[:-1] + "+00:00")

    # Test empty string
    res2 = normalize_timestamp("")
    assert res2.endswith("Z")
    assert datetime.fromisoformat(res2[:-1] + "+00:00")

def test_normalize_timestamp_naive():
    res = normalize_timestamp("2024-01-01T12:00:00")
    assert res == "2024-01-01T12:00:00Z"

def test_normalize_timestamp_z_suffix():
    res = normalize_timestamp("2024-01-01T12:00:00Z")
    assert res.endswith("Z") or "+00:00" in res

def test_normalize_timestamp_timezone_aware():
    res = normalize_timestamp("2024-01-01T12:00:00-05:00")
    assert "+00:00" in res or "-" in res[10:]
