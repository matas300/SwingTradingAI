import numpy as np
import pandas as pd

from swing_trading.service import format_price, grade_from_confidence

def test_format_price():
    # Test None and missing values
    assert format_price(None) == "-"
    assert format_price(float("nan")) == "-"
    assert format_price(np.nan) == "-"
    assert format_price(pd.NA) == "-"

    # Test standard floats
    assert format_price(12.34) == "12.34"
    assert format_price(12.3) == "12.30"

    # Test rounding behavior
    assert format_price(12.345) == "12.35"
    assert format_price(12.344) == "12.34"

    # Test integer conversion
    assert format_price(10) == "10.00"
    assert format_price(0) == "0.00"

    # Test negative numbers
    assert format_price(-5.67) == "-5.67"
    assert format_price(-10) == "-10.00"

def test_grade_from_confidence_returns_A_for_high_values():
    assert grade_from_confidence(0.85) == "A"
    assert grade_from_confidence(0.82) == "A"

def test_grade_from_confidence_returns_B_for_medium_high_values():
    assert grade_from_confidence(0.75) == "B"
    assert grade_from_confidence(0.70) == "B"
    assert grade_from_confidence(0.819) == "B"

def test_grade_from_confidence_returns_C_for_medium_values():
    assert grade_from_confidence(0.65) == "C"
    assert grade_from_confidence(0.58) == "C"
    assert grade_from_confidence(0.699) == "C"

def test_grade_from_confidence_returns_dash_for_low_values():
    assert grade_from_confidence(0.50) == "-"
    assert grade_from_confidence(0.0) == "-"
    assert grade_from_confidence(0.579) == "-"
