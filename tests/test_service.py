import numpy as np
import pandas as pd

from swing_trading.service import format_price

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
