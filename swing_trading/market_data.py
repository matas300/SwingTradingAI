from __future__ import annotations

from datetime import date, datetime, time as clock_time
from zoneinfo import ZoneInfo

import pandas as pd
import ta
import yfinance as yf

from .models import FeatureSnapshot, MarketContext

US_MARKET_TIMEZONE = ZoneInfo("America/New_York")
US_MARKET_CLOSE = clock_time(16, 15)


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if isinstance(frame.columns, pd.MultiIndex):
        first_level = frame.columns.get_level_values(0)
        if {"Open", "High", "Low", "Close", "Volume"}.issubset(first_level):
            frame.columns = first_level
        else:
            frame.columns = frame.columns.get_level_values(-1)
    if frame.columns.has_duplicates:
        frame = frame.T.groupby(level=0, sort=False).first().T
    return frame


def keep_confirmed_daily_history(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    last_index = pd.Timestamp(frame.index[-1])
    if getattr(last_index, "tzinfo", None) is not None:
        last_index = last_index.tz_convert(None)
    now_market = datetime.now(US_MARKET_TIMEZONE)
    if last_index.date() == now_market.date() and now_market.time() < US_MARKET_CLOSE and len(frame) > 1:
        return frame.iloc[:-1].copy()
    return frame


def download_prices(ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    frame = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    frame = normalize_columns(frame)
    frame = frame.sort_index()
    if getattr(frame.index, "tz", None) is not None:
        frame.index = frame.index.tz_convert(None)
    frame = keep_confirmed_daily_history(frame)
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise RuntimeError(f"{ticker}: missing columns {missing}")
    if frame.empty:
        raise RuntimeError(f"{ticker}: no daily data returned")
    return frame


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    data["ema9"] = data["Close"].ewm(span=9, adjust=False).mean()
    data["ema21"] = data["Close"].ewm(span=21, adjust=False).mean()
    data["sma50"] = data["Close"].rolling(50).mean()
    data["sma200"] = data["Close"].rolling(200).mean()
    data["rsi"] = ta.momentum.RSIIndicator(data["Close"], window=14).rsi()
    data["atr"] = ta.volatility.AverageTrueRange(
        data["High"],
        data["Low"],
        data["Close"],
        window=14,
    ).average_true_range()
    data["adx"] = ta.trend.ADXIndicator(
        data["High"],
        data["Low"],
        data["Close"],
        window=14,
    ).adx()
    data["vol_avg20"] = data["Volume"].rolling(20).mean()
    data["recent_high"] = data["High"].rolling(20).max().shift(1)
    data["recent_low"] = data["Low"].rolling(20).min().shift(1)
    data["support"] = data["Low"].rolling(20).min().shift(1)
    data["resistance"] = data["High"].rolling(20).max().shift(1)
    data["volatility_20d"] = data["Close"].pct_change().rolling(20).std() * (252 ** 0.5)
    data["drawdown_63d"] = data["Close"] / data["Close"].rolling(63).max() - 1.0
    data["ret_1m"] = data["Close"].pct_change(21)
    data["ret_3m"] = data["Close"].pct_change(63)
    return data


def detect_trend(close_value: float, sma50: float, ema9: float, ema21: float) -> str:
    if pd.isna(sma50) or pd.isna(ema21):
        return "LATERAL"
    if close_value > sma50 and ema9 >= ema21:
        return "UP"
    if close_value < sma50 and ema9 <= ema21:
        return "DOWN"
    return "LATERAL"


def build_market_context(period: str = "1y") -> tuple[MarketContext, pd.DataFrame]:
    spy = add_indicators(download_prices("SPY", period=period))
    qqq = add_indicators(download_prices("QQQ", period=period))
    vix = download_prices("^VIX", period=period)
    vix["sma20"] = vix["Close"].rolling(20).mean()

    spy_close = float(spy["Close"].iloc[-1])
    qqq_close = float(qqq["Close"].iloc[-1])
    vix_close = float(vix["Close"].iloc[-1])
    spy_sma50 = float(spy["sma50"].iloc[-1])
    qqq_sma50 = float(qqq["sma50"].iloc[-1])
    vix_sma20 = float(vix["sma20"].iloc[-1])

    benchmark_trend = "UP" if spy_close > spy_sma50 else "DOWN"
    growth_trend = "UP" if qqq_close > qqq_sma50 else "DOWN"
    warnings: list[str] = []
    if benchmark_trend == "UP" and growth_trend == "UP" and vix_close <= 18.0:
        risk_mode = "RISK_ON"
    elif (benchmark_trend == "DOWN" and growth_trend == "DOWN") or vix_close >= 22.0:
        risk_mode = "RISK_OFF"
    else:
        risk_mode = "MIXED"

    if benchmark_trend == "DOWN":
        warnings.append("SPY below 50-day trend")
    if growth_trend == "DOWN":
        warnings.append("QQQ below 50-day trend")
    if vix_close >= 22.0:
        warnings.append("VIX elevated")

    benchmark = pd.DataFrame(index=spy.index)
    benchmark["spy_close"] = spy["Close"]
    benchmark["spy_ret_1m"] = spy["ret_1m"]
    benchmark["spy_ret_3m"] = spy["ret_3m"]

    return (
        MarketContext(
            benchmark_trend=benchmark_trend,
            growth_trend=growth_trend,
            benchmark_close=spy_close,
            benchmark_sma50=spy_sma50,
            growth_close=qqq_close,
            growth_sma50=qqq_sma50,
            vix_close=vix_close,
            vix_sma20=vix_sma20,
            risk_mode=risk_mode,
            warnings=warnings,
        ),
        benchmark,
    )


def get_next_earnings_date(ticker: str) -> date | None:
    try:
        calendar = yf.Ticker(ticker).calendar
    except Exception:
        return None

    if isinstance(calendar, pd.DataFrame) and not calendar.empty:
        for column in calendar.columns:
            if "Earnings Date" in str(column):
                value = calendar.iloc[0][column]
                if hasattr(value, "date"):
                    return value.date()
    if isinstance(calendar, dict):
        for key, values in calendar.items():
            if "Earnings Date" in str(key) and values:
                value = values[0]
                if hasattr(value, "date"):
                    return value.date()
    return None


def build_feature_history(
    ticker: str,
    price_frame: pd.DataFrame,
    benchmark: pd.DataFrame,
    market_context: MarketContext,
) -> list[FeatureSnapshot]:
    aligned_benchmark = benchmark.reindex(price_frame.index).ffill()
    history: list[FeatureSnapshot] = []
    previous_close: float | None = None

    for idx, row in price_frame.iterrows():
        if any(pd.isna(row[column]) for column in ("atr", "adx", "rsi", "ema9", "ema21", "sma50")):
            continue
        bench_row = aligned_benchmark.loc[idx] if idx in aligned_benchmark.index else None
        bench_ret_1m = float(bench_row["spy_ret_1m"]) if bench_row is not None and pd.notna(bench_row["spy_ret_1m"]) else 0.0
        bench_ret_3m = float(bench_row["spy_ret_3m"]) if bench_row is not None and pd.notna(bench_row["spy_ret_3m"]) else 0.0
        stock_ret_1m = float(row["ret_1m"]) if pd.notna(row["ret_1m"]) else 0.0
        stock_ret_3m = float(row["ret_3m"]) if pd.notna(row["ret_3m"]) else 0.0
        volume_ratio = float(row["Volume"] / row["vol_avg20"]) if pd.notna(row["vol_avg20"]) and row["vol_avg20"] else 1.0
        atr = float(row["atr"]) if pd.notna(row["atr"]) else 0.0
        close = float(row["Close"])
        support = float(row["support"]) if pd.notna(row["support"]) else None
        resistance = float(row["resistance"]) if pd.notna(row["resistance"]) else None
        breakout = None
        if pd.notna(row["recent_high"]) and close > float(row["recent_high"]) and volume_ratio >= 1.15 and row["adx"] >= 20:
            breakout = "bullish"
        elif pd.notna(row["recent_low"]) and close < float(row["recent_low"]) and volume_ratio >= 1.15 and row["adx"] >= 20:
            breakout = "bearish"

        trend = detect_trend(close, float(row["sma50"]), float(row["ema9"]), float(row["ema21"]))
        gap_pct = ((float(row["Open"]) - previous_close) / previous_close) if previous_close else 0.0
        history.append(
            FeatureSnapshot(
                ticker=ticker,
                session_date=pd.Timestamp(idx).date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=close,
                volume=float(row["Volume"]),
                atr=atr,
                adx=float(row["adx"]),
                rsi=float(row["rsi"]),
                ema_fast=float(row["ema9"]),
                ema_slow=float(row["ema21"]),
                sma50=float(row["sma50"]),
                sma200=float(row["sma200"]) if pd.notna(row["sma200"]) else None,
                support=support,
                resistance=resistance,
                recent_high=float(row["recent_high"]) if pd.notna(row["recent_high"]) else None,
                recent_low=float(row["recent_low"]) if pd.notna(row["recent_low"]) else None,
                volume_ratio=volume_ratio,
                volatility_20d=float(row["volatility_20d"]) if pd.notna(row["volatility_20d"]) else 0.0,
                drawdown_63d=float(row["drawdown_63d"]) if pd.notna(row["drawdown_63d"]) else 0.0,
                relative_strength_1m=stock_ret_1m - bench_ret_1m,
                relative_strength_3m=stock_ret_3m - bench_ret_3m,
                close_vs_ema21_atr=((close - float(row["ema21"])) / atr) if atr else 0.0,
                close_to_support_atr=((close - support) / atr) if atr and support is not None else None,
                close_to_resistance_atr=((resistance - close) / atr) if atr and resistance is not None else None,
                breakout=breakout,
                trend=trend,
                market_regime=market_context.risk_mode,
                gap_pct=gap_pct,
            )
        )
        previous_close = close
    return history
