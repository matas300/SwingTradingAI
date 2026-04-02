from __future__ import annotations

import re
from datetime import datetime, timezone

TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,11}$")


def normalize_ticker(value: str) -> str:
    ticker = str(value or "").strip().upper()
    if not ticker or not TICKER_RE.fullmatch(ticker):
        raise ValueError(f"Invalid ticker: {value!r}")
    return ticker


def normalize_ticker_list(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        ticker = normalize_ticker(value)
        if ticker not in seen:
            seen.add(ticker)
            deduped.append(ticker)
    return deduped


def ensure_positive_number(value: float, field_name: str) -> float:
    number = float(value)
    if number <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")
    return number


def ensure_non_negative_number(value: float | None, field_name: str) -> float:
    number = float(value or 0.0)
    if number < 0:
        raise ValueError(f"{field_name} cannot be negative.")
    return number


def normalize_timestamp(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        return parsed.replace(microsecond=0).isoformat() + "Z"
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
