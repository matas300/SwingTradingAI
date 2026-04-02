import pytest
from datetime import datetime
from swing_trading.validation import normalize_timestamp

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
