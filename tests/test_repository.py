from datetime import date
import pytest
from swing_trading.repository import parse_date, SQLiteRepository

def test_parse_date_valid():
    assert parse_date("2023-01-01") == date(2023, 1, 1)
    assert parse_date("2023-01-01T12:00:00Z") == date(2023, 1, 1)

def test_parse_date_none_or_empty():
    assert parse_date(None) is None
    assert parse_date("") is None

def test_parse_date_invalid():
    assert parse_date("not-a-date") is None
    assert parse_date("2023-13-01") is None

def test_export_table_rows_valid_table(tmp_path):
    db_path = tmp_path / "test.db"
    repo = SQLiteRepository(db_path)
    repo.ensure_schema()

    # Should not raise an exception
    repo.export_table_rows("users")

def test_export_table_rows_invalid_table_sql_injection(tmp_path):
    db_path = tmp_path / "test.db"
    repo = SQLiteRepository(db_path)
    repo.ensure_schema()

    with pytest.raises(ValueError, match="Invalid table name"):
        repo.export_table_rows("users; DROP TABLE users;")
