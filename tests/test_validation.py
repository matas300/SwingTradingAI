import pytest
from swing_trading.validation import ensure_non_negative_number

def test_ensure_non_negative_number_positive():
    assert ensure_non_negative_number(5.0, "Test Field") == 5.0

def test_ensure_non_negative_number_zero():
    assert ensure_non_negative_number(0.0, "Test Field") == 0.0

def test_ensure_non_negative_number_none():
    assert ensure_non_negative_number(None, "Test Field") == 0.0

def test_ensure_non_negative_number_negative():
    with pytest.raises(ValueError, match="Test Field cannot be negative."):
        ensure_non_negative_number(-1.0, "Test Field")
