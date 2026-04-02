from swing_trading.service import grade_from_confidence

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
