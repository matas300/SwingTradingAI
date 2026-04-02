import pytest
from swing_trading.repository import SQLiteRepository

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

    # Attempt SQL injection
    with pytest.raises(ValueError, match="Invalid table name: users; DROP TABLE users;"):
        repo.export_table_rows("users; DROP TABLE users;")

def test_export_table_rows_invalid_table_random(tmp_path):
    db_path = tmp_path / "test.db"
    repo = SQLiteRepository(db_path)
    repo.ensure_schema()

    with pytest.raises(ValueError, match="Invalid table name: random_table"):
        repo.export_table_rows("random_table")
