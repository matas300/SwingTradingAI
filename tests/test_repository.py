import pytest
from datetime import datetime
from swing_trading.repository import parse_timestamp

def test_parse_timestamp_valid():
    assert parse_timestamp("2023-01-01T12:00:00Z") == datetime.fromisoformat("2023-01-01T12:00:00+00:00")
    assert parse_timestamp("2023-01-01T12:00:00+00:00") == datetime.fromisoformat("2023-01-01T12:00:00+00:00")
    assert parse_timestamp("2023-01-01") == datetime.fromisoformat("2023-01-01")

def test_parse_timestamp_empty():
    assert parse_timestamp(None) is None
    assert parse_timestamp("") is None

def test_parse_timestamp_invalid():
    assert parse_timestamp("invalid-date-string") is None
