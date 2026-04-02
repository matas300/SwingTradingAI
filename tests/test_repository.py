from datetime import date
import pytest
from swing_trading.repository import parse_date

def test_parse_date_valid():
    assert parse_date("2023-01-01") == date(2023, 1, 1)
    assert parse_date("2023-01-01T12:00:00Z") == date(2023, 1, 1)

def test_parse_date_none_or_empty():
    assert parse_date(None) is None
    assert parse_date("") is None

def test_parse_date_invalid():
    assert parse_date("not-a-date") is None
    assert parse_date("2023-13-01") is None
