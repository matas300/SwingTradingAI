from __future__ import annotations

import argparse
import math
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date as calendar_date
from datetime import datetime, time as clock_time, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Literal
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import pandas as pd
import ta
import yfinance as yf


Signal = Literal["LONG", "SHORT", "NO TRADE"]
Trend = Literal["UP", "DOWN", "LATERAL", "UNKNOWN"]
RiskMode = Literal["RISK_ON", "MIXED", "RISK_OFF"]
NewsLevel = Literal["LOW", "MODERATE", "HIGH", "EXTREME"]
NewsStance = Literal["NEUTRAL", "VOLATILE", "RELIEF"]
HeadlineScope = Literal["macro", "ticker"]

DEFAULT_TICKERS = ("NVDA", "AAPL", "DUOL", "CRM", "MSFT", "RACE")
TOP_100_US_TICKERS = (
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "BRK-B", "AVGO", "TSLA", "WMT",
    "JPM", "V", "MA", "UNH", "XOM", "COST", "PG", "JNJ", "HD", "BAC",
    "ABBV", "KO", "NFLX", "CRM", "ORCL", "CSCO", "ABT", "ACN", "MCD", "AMD",
    "TMO", "LIN", "WFC", "DHR", "MRK", "DIS", "GE", "QCOM", "IBM", "TXN",
    "CAT", "AMGN", "GS", "INTU", "BLK", "AMAT", "NOW", "BKNG", "SPGI", "RTX",
    "HON", "LOW", "PGR", "SYK", "PLD", "SCHW", "ADP", "ELV", "CVX", "MDT",
    "LRCX", "C", "ETN", "TJX", "MMC", "MO", "CB", "GILD", "CMCSA", "DE",
    "COP", "NEE", "USB", "SO", "ICE", "FI", "PM", "APH", "MU", "PANW",
    "ADI", "KLAC", "ANET", "MDLZ", "CME", "EQIX", "UPS", "BX", "TT", "WM",
    "AON", "MSI", "CDNS", "PYPL", "SNPS", "CRWD", "ADSK", "ABNB", "UBER", "NKE",
)
REQUIRED_COLUMNS = ("Open", "High", "Low", "Close", "Volume")
US_MARKET_TIMEZONE = ZoneInfo("America/New_York")
US_MARKET_CLOSE = clock_time(16, 15)

MACRO_NEWS_QUERIES: tuple[str, ...] = (
    "Trump tariffs stock market",
    "war oil stock market",
    "sanctions stock market",
    "Federal Reserve inflation stock market",
    "China tariffs tech stocks",
)

TICKER_ALIASES: dict[str, tuple[str, ...]] = {
    "AAPL": ("apple", "iphone"),
    "CRM": ("salesforce",),
    "DUOL": ("duolingo",),
    "MSFT": ("microsoft", "azure"),
    "NVDA": ("nvidia", "jensen huang"),
    "RACE": ("ferrari",),
}

NEWS_THEME_RULES: dict[str, dict[str, tuple[str, ...] | float]] = {
    "War/conflict": {
        "keywords": (
            "war",
            "conflict",
            "attack",
            "missile",
            "drone strike",
            "bombing",
            "invasion",
            "troops",
            "military",
            "hostilities",
        ),
        "weight": 3.0,
    },
    "Trump/politics": {
        "keywords": (
            "trump",
            "white house",
            "election",
            "administration",
            "executive order",
        ),
        "weight": 1.8,
    },
    "Trade/tariffs": {
        "keywords": (
            "tariff",
            "tariffs",
            "trade war",
            "duties",
            "duty",
            "export control",
            "export curb",
            "export curbs",
            "retaliation",
            "sanction",
            "sanctions",
        ),
        "weight": 2.5,
    },
    "Rates/inflation": {
        "keywords": (
            "fed",
            "federal reserve",
            "powell",
            "inflation",
            "cpi",
            "pce",
            "rate hike",
            "rate cut",
            "treasury yield",
            "bond yields",
        ),
        "weight": 1.6,
    },
    "Energy/oil": {
        "keywords": (
            "oil",
            "crude",
            "opec",
            "natural gas",
            "supply shock",
        ),
        "weight": 1.4,
    },
    "Legal/regulation": {
        "keywords": (
            "antitrust",
            "lawsuit",
            "probe",
            "investigation",
            "sec",
            "doj",
            "ftc",
            "regulator",
            "ban",
        ),
        "weight": 1.5,
    },
    "Company event": {
        "keywords": (
            "earnings",
            "guidance",
            "forecast",
            "outlook",
            "warning",
            "downgrade",
            "hack",
            "data breach",
            "outage",
            "recall",
        ),
        "weight": 1.3,
    },
}

RELIEF_KEYWORDS = (
    "ceasefire",
    "truce",
    "peace talks",
    "de-escalation",
    "trade deal",
    "tariff pause",
    "tariff delay",
    "exemption",
    "waiver",
    "cooling inflation",
    "inflation eases",
)


@dataclass(frozen=True)
class ScannerConfig:
    tickers: tuple[str, ...] = DEFAULT_TICKERS
    daily_period: str = "2y"
    daily_interval: str = "1d"
    news_enabled: bool = False
    benchmark_ticker: str = "SPY"
    growth_benchmark_ticker: str = "QQQ"
    volatility_ticker: str = "^VIX"
    rsi_window: int = 14
    atr_window: int = 14
    adx_window: int = 14
    volume_window: int = 20
    structure_window: int = 20
    fast_ema: int = 9
    slow_ema: int = 21
    sma_medium: int = 50
    sma_slow: int = 200
    min_adx: float = 20.0
    breakout_tolerance: float = 0.015
    atr_multiplier: float = 1.6
    rr_ratio: float = 2.2
    min_structure_stop_atr: float = 0.6
    max_structure_stop_atr: float = 2.8
    risk_per_trade: float = 0.01
    account_size: float = 10_000.0
    high_volume_threshold: float = 1.35
    low_volume_threshold: float = 0.75
    news_lookback_days: int = 5
    max_headlines_per_query: int = 4
    max_macro_headlines: int = 12
    max_ticker_headlines: int = 8
    max_download_retries: int = 3
    retry_sleep_seconds: float = 1.0
    hard_event_risk_threshold: float = 8.0
    elevated_event_risk_threshold: float = 5.0
    vix_risk_on_ceiling: float = 18.0
    vix_risk_off_floor: float = 22.0
    chart_points: int = 90
    scan_workers: int = 3


@dataclass
class DailyAnalysis:
    trend: Trend
    close: float
    support: float | None
    resistance: float | None
    divergence: str | None
    volume_label: str
    bull_score: int
    bear_score: int
    rsi: float
    atr: float
    atr_pct: float
    adx: float
    macd: float
    macd_signal: float
    ema_fast: float
    ema_slow: float
    sma50: float
    sma200: float
    month_return: float
    quarter_return: float
    relative_strength_1m: float
    relative_strength_3m: float
    breakout_ready: bool
    breakdown_ready: bool


@dataclass
class MarketContext:
    benchmark_trend: Trend
    growth_trend: Trend
    benchmark_close: float
    benchmark_sma50: float
    growth_close: float
    growth_sma50: float
    vix_close: float
    vix_sma20: float
    risk_mode: RiskMode
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Headline:
    scope: HeadlineScope
    source: str
    title: str
    link: str
    published_at: datetime | None
    age_hours: float | None


@dataclass(frozen=True)
class ScoredHeadline:
    headline: Headline
    risk_score: float
    relief_score: float
    themes: tuple[str, ...]


@dataclass
class NewsImpact:
    ticker: str
    level: NewsLevel
    stance: NewsStance
    risk_score: float
    relief_score: float
    net_risk_score: float
    size_multiplier: float
    matched_themes: list[str]
    headlines: list[ScoredHeadline]
    macro_count: int
    ticker_count: int


@dataclass
class EarningsContext:
    next_earnings_date: calendar_date | None
    days_to_earnings: int | None
    label: str
    warning: str | None


@dataclass(frozen=True)
class PriceChartPoint:
    date: calendar_date
    close: float
    sma50: float | None
    sma200: float | None


@dataclass
class TradeSetup:
    ticker: str
    analysis_date: calendar_date
    signal: Signal
    confidence: float
    technical_signal: Signal
    technical_confidence: float
    grade: str
    entry: float | None
    stop: float | None
    target: float | None
    risk_per_share: float | None
    reward_per_share: float | None
    position_size: int | None
    position_multiplier: float
    daily: DailyAnalysis
    market: MarketContext
    macro_news: NewsImpact
    company_news: NewsImpact
    earnings: EarningsContext
    price_chart: list[PriceChartPoint] = field(default_factory=list)
    technical_reasons: list[str] = field(default_factory=list)
    technical_warnings: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    commentary: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Daily swing trading scanner with market regime and macro event risk filtering."
    )
    parser.add_argument("--tickers", nargs="+", default=list(DEFAULT_TICKERS), help="Tickers to scan.")
    parser.add_argument("--daily-period", type=str, default="2y", help="Yahoo period for daily candles, e.g. 3mo, 6mo, 1y, 2y.")
    parser.add_argument("--account-size", type=float, default=10_000.0, help="Reference account size.")
    parser.add_argument("--risk-per-trade", type=float, default=0.01, help="Fraction of capital risked per trade.")
    parser.add_argument(
        "--news-lookback-days",
        type=int,
        default=5,
        help="Recent days of headlines used for macro and ticker event risk.",
    )
    parser.add_argument(
        "--enable-news",
        action="store_true",
        help="Enable macro and company news filtering. Disabled by default.",
    )
    parser.add_argument(
        "--export-csv",
        type=str,
        default="scan_summary.csv",
        help="CSV export path. Set empty string to disable export.",
    )
    args, _ = parser.parse_known_args()
    return args


def download_ohlcv(
    ticker: str,
    *,
    period: str,
    interval: str,
    max_retries: int,
    retry_sleep_seconds: float,
) -> pd.DataFrame:
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            df = yf.download(
                ticker,
                period=period,
                interval=interval,
                auto_adjust=True,
                progress=False,
                threads=False,
            )
            if isinstance(df.columns, pd.MultiIndex):
                first_level = df.columns.get_level_values(0)
                if set(REQUIRED_COLUMNS).issubset(first_level):
                    df.columns = first_level
                else:
                    df.columns = df.columns.get_level_values(-1)
            if df.columns.has_duplicates:
                df = df.T.groupby(level=0, sort=False).first().T
            df = df.sort_index()
            if interval == "1d":
                df = keep_confirmed_daily_history(df)
            missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
            if missing:
                raise ValueError(f"{ticker} missing required columns: {missing}")
            if df.empty:
                raise ValueError(f"{ticker} returned no data for {period} / {interval}")
            return df
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(retry_sleep_seconds * attempt)

    raise RuntimeError(f"Unable to download data for {ticker} ({period}, {interval}): {last_error}")


def keep_confirmed_daily_history(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    last_index = pd.Timestamp(df.index[-1])
    last_session_date = last_index.date()
    now_market = datetime.now(US_MARKET_TIMEZONE)

    if last_session_date == now_market.date() and now_market.time() < US_MARKET_CLOSE and len(df) > 1:
        return df.iloc[:-1].copy()
    return df


def effective_window(requested: int, available: int, *, minimum: int = 2) -> int:
    if available <= 0:
        return minimum
    return min(available, max(minimum, min(requested, available)))


def required_history_bars(config: ScannerConfig) -> int:
    return max(config.structure_window + 2, config.volume_window + 2, config.sma_medium + 5, 30)


def validate_analysis_frame(df: pd.DataFrame, label: str, config: ScannerConfig) -> None:
    if len(df) < required_history_bars(config):
        raise RuntimeError(f"{label} has too little history: {len(df)} rows")

    last = df.iloc[-1]
    required_fields = ("rsi", "ema_fast", "ema_slow", "atr", "adx", "macd", "macd_signal", "vol_avg", "sma50")
    missing = [field for field in required_fields if field not in df.columns or pd.isna(last[field])]
    if missing:
        raise RuntimeError(f"{label} latest row is missing indicators: {missing}")


def add_indicators(df: pd.DataFrame, config: ScannerConfig) -> pd.DataFrame:
    data = df.copy()
    available = len(data)
    sma_medium_window = effective_window(config.sma_medium, available, minimum=5)
    sma_slow_window = effective_window(config.sma_slow, available, minimum=max(sma_medium_window + 1, 10))
    volume_window = effective_window(config.volume_window, available, minimum=5)
    structure_window = effective_window(config.structure_window, available, minimum=5)

    macd_indicator = ta.trend.MACD(data["Close"])

    data["rsi"] = ta.momentum.RSIIndicator(data["Close"], window=config.rsi_window).rsi()
    data["ema_fast"] = data["Close"].ewm(span=config.fast_ema, adjust=False).mean()
    data["ema_slow"] = data["Close"].ewm(span=config.slow_ema, adjust=False).mean()
    data["sma50"] = data["Close"].rolling(sma_medium_window, min_periods=sma_medium_window).mean()
    data["sma200"] = data["Close"].rolling(sma_slow_window, min_periods=sma_slow_window).mean()
    data["atr"] = ta.volatility.AverageTrueRange(
        data["High"],
        data["Low"],
        data["Close"],
        window=config.atr_window,
    ).average_true_range()
    data["atr_pct"] = data["atr"] / data["Close"]
    data["adx"] = ta.trend.ADXIndicator(
        data["High"],
        data["Low"],
        data["Close"],
        window=config.adx_window,
    ).adx()
    data["macd"] = macd_indicator.macd()
    data["macd_signal"] = macd_indicator.macd_signal()
    data["vol_avg"] = data["Volume"].rolling(volume_window, min_periods=volume_window).mean()
    data["recent_high"] = data["High"].rolling(structure_window, min_periods=structure_window).max()
    data["recent_low"] = data["Low"].rolling(structure_window, min_periods=structure_window).min()
    data["sma50_slope"] = data["sma50"].diff(5)

    return data


def trailing_return(series: pd.Series, lookback: int) -> float:
    if len(series) <= lookback:
        return 0.0
    previous = float(series.iloc[-lookback - 1])
    current = float(series.iloc[-1])
    if previous == 0:
        return 0.0
    return current / previous - 1.0


def detect_trend(df: pd.DataFrame) -> Trend:
    last = df.iloc[-1]

    if pd.isna(last["sma50"]) or pd.isna(last["ema_fast"]) or pd.isna(last["ema_slow"]):
        return "UNKNOWN"

    slope_up = pd.notna(last["sma50_slope"]) and last["sma50_slope"] > 0
    slope_down = pd.notna(last["sma50_slope"]) and last["sma50_slope"] < 0
    above_long_term = pd.isna(last["sma200"]) or last["sma50"] > last["sma200"]
    below_long_term = pd.isna(last["sma200"]) or last["sma50"] < last["sma200"]

    if last["Close"] > last["sma50"] and last["ema_fast"] > last["ema_slow"] and slope_up and above_long_term:
        return "UP"
    if last["Close"] < last["sma50"] and last["ema_fast"] < last["ema_slow"] and slope_down and below_long_term:
        return "DOWN"
    return "LATERAL"


def detect_divergence(df: pd.DataFrame, lookback: int = 7) -> str | None:
    sample = df[["Close", "rsi"]].tail(lookback).dropna()
    if len(sample) < lookback:
        return None

    price_delta = sample["Close"].iloc[-1] - sample["Close"].iloc[0]
    rsi_delta = sample["rsi"].iloc[-1] - sample["rsi"].iloc[0]

    if price_delta > 0 and rsi_delta < -3:
        return "Bearish divergence"
    if price_delta < 0 and rsi_delta > 3:
        return "Bullish divergence"
    return None


def classify_volume(last_volume: float, average_volume: float, config: ScannerConfig) -> str:
    if pd.isna(average_volume) or average_volume <= 0:
        return "Volume N/A"
    if last_volume > average_volume * config.high_volume_threshold:
        return "Volume high"
    if last_volume < average_volume * config.low_volume_threshold:
        return "Volume low"
    return "Volume normal"


def safe_float(value: float | int | None) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def analyze_daily(df: pd.DataFrame, benchmark_df: pd.DataFrame, config: ScannerConfig) -> DailyAnalysis:
    last = df.iloc[-1]
    trend = detect_trend(df)
    divergence = detect_divergence(df)
    support = safe_float(df["Low"].rolling(config.structure_window).min().shift(1).iloc[-1])
    resistance = safe_float(df["High"].rolling(config.structure_window).max().shift(1).iloc[-1])
    volume_label = classify_volume(float(last["Volume"]), float(last["vol_avg"]), config)

    month_return = trailing_return(df["Close"], 21)
    quarter_return = trailing_return(df["Close"], 63)
    benchmark_month_return = trailing_return(benchmark_df["Close"], 21)
    benchmark_quarter_return = trailing_return(benchmark_df["Close"], 63)
    rs_1m = month_return - benchmark_month_return
    rs_3m = quarter_return - benchmark_quarter_return

    breakout_ready = resistance is not None and last["Close"] >= resistance * (1 - config.breakout_tolerance)
    breakdown_ready = support is not None and last["Close"] <= support * (1 + config.breakout_tolerance)

    bull_checks = [
        trend == "UP",
        pd.notna(last["sma50"]) and last["Close"] > last["sma50"],
        pd.notna(last["sma200"]) and last["Close"] > last["sma200"],
        last["ema_fast"] > last["ema_slow"],
        last["macd"] > last["macd_signal"],
        50 <= last["rsi"] <= 72,
        last["adx"] >= config.min_adx,
        rs_1m > 0,
        rs_3m > -0.01,
        volume_label != "Volume low",
        breakout_ready,
    ]
    bear_checks = [
        trend == "DOWN",
        pd.notna(last["sma50"]) and last["Close"] < last["sma50"],
        pd.notna(last["sma200"]) and last["Close"] < last["sma200"],
        last["ema_fast"] < last["ema_slow"],
        last["macd"] < last["macd_signal"],
        28 <= last["rsi"] <= 50,
        last["adx"] >= config.min_adx,
        rs_1m < 0,
        rs_3m < 0.01,
        volume_label != "Volume low",
        breakdown_ready,
    ]

    if divergence == "Bullish divergence":
        bull_checks.append(True)
    if divergence == "Bearish divergence":
        bear_checks.append(True)

    return DailyAnalysis(
        trend=trend,
        close=float(last["Close"]),
        support=support,
        resistance=resistance,
        divergence=divergence,
        volume_label=volume_label,
        bull_score=sum(bool(item) for item in bull_checks),
        bear_score=sum(bool(item) for item in bear_checks),
        rsi=float(last["rsi"]),
        atr=float(last["atr"]),
        atr_pct=float(last["atr_pct"]),
        adx=float(last["adx"]),
        macd=float(last["macd"]),
        macd_signal=float(last["macd_signal"]),
        ema_fast=float(last["ema_fast"]),
        ema_slow=float(last["ema_slow"]),
        sma50=float(last["sma50"]),
        sma200=float(last["sma200"]),
        month_return=month_return,
        quarter_return=quarter_return,
        relative_strength_1m=rs_1m,
        relative_strength_3m=rs_3m,
        breakout_ready=breakout_ready,
        breakdown_ready=breakdown_ready,
    )


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None


def headline_age_hours(timestamp: datetime | None) -> float | None:
    if timestamp is None:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - timestamp).total_seconds() / 3600, 0.0)


def recency_weight(age_hours: float | None) -> float:
    if age_hours is None:
        return 0.5
    if age_hours <= 24:
        return 1.0
    if age_hours <= 72:
        return 0.8
    if age_hours <= 120:
        return 0.6
    return 0.4


def dedupe_headlines(headlines: list[Headline]) -> list[Headline]:
    seen: set[str] = set()
    unique: list[Headline] = []
    for headline in sorted(
        headlines,
        key=lambda item: item.published_at or datetime(1970, 1, 1, tzinfo=timezone.utc),
        reverse=True,
    ):
        key = headline.title.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(headline)
    return unique


def extract_source_from_title(title: str) -> str:
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return "Google News"


def headline_matches_ticker(title: str, ticker: str) -> bool:
    lowered = title.lower()
    symbol_pattern = re.compile(rf"\b{re.escape(ticker.lower())}\b")
    if symbol_pattern.search(lowered):
        return True
    return any(alias in lowered for alias in TICKER_ALIASES.get(ticker.upper(), ()))


def fetch_macro_headlines(config: ScannerConfig) -> list[Headline]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.news_lookback_days)
    headlines: list[Headline] = []

    for query in MACRO_NEWS_QUERIES:
        url = (
            "https://news.google.com/rss/search?q="
            f"{quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        )
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=20) as response:
                root = ET.fromstring(response.read())
        except Exception:
            continue

        channel = root.find("channel")
        if channel is None:
            continue

        count = 0
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            published_at = parse_datetime(item.findtext("pubDate"))
            if published_at is not None and published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            if published_at is not None and published_at < cutoff:
                continue
            headlines.append(
                Headline(
                    scope="macro",
                    source=extract_source_from_title(title),
                    title=title,
                    link=link,
                    published_at=published_at,
                    age_hours=headline_age_hours(published_at),
                )
            )
            count += 1
            if count >= config.max_headlines_per_query:
                break

    unique = dedupe_headlines(headlines)
    return unique[: config.max_macro_headlines]


def fetch_ticker_headlines(ticker: str, config: ScannerConfig) -> list[Headline]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.news_lookback_days)
    headlines: list[Headline] = []

    try:
        items = yf.Ticker(ticker).news
    except Exception:
        return headlines

    for item in items:
        content = item.get("content", {}) if isinstance(item, dict) else {}
        title = (content.get("title") or "").strip()
        if not title:
            continue
        if not headline_matches_ticker(title, ticker):
            continue
        published_at = parse_datetime(content.get("pubDate") or content.get("displayTime"))
        if published_at is not None and published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        if published_at is not None and published_at < cutoff:
            continue
        provider = content.get("provider", {})
        source = provider.get("displayName") if isinstance(provider, dict) else ""
        canonical = content.get("canonicalUrl", {})
        click_through = content.get("clickThroughUrl", {})
        link = ""
        if isinstance(canonical, dict):
            link = canonical.get("url") or ""
        if not link and isinstance(click_through, dict):
            link = click_through.get("url") or ""
        headlines.append(
            Headline(
                scope="ticker",
                source=source or "Yahoo Finance",
                title=title,
                link=link,
                published_at=published_at,
                age_hours=headline_age_hours(published_at),
            )
        )
        if len(headlines) >= config.max_ticker_headlines:
            break

    return dedupe_headlines(headlines)


def score_headline(headline: Headline) -> ScoredHeadline | None:
    title = headline.title.lower()
    if not title:
        return None

    risk_score = 0.0
    relief_score = 0.0
    matched_themes: list[str] = []
    freshness = recency_weight(headline.age_hours)

    for theme, rule in NEWS_THEME_RULES.items():
        keywords = rule["keywords"]
        if any(keyword in title for keyword in keywords):
            risk_score += float(rule["weight"]) * freshness
            matched_themes.append(theme)

    if any(keyword in title for keyword in RELIEF_KEYWORDS):
        relief_score += 1.5 * freshness
        matched_themes.append("Relief/de-escalation")

    if headline.source.lower() in {"reuters", "ap", "associated press"}:
        risk_score *= 1.05
        relief_score *= 1.05

    if risk_score == 0 and relief_score == 0:
        return None

    return ScoredHeadline(
        headline=headline,
        risk_score=risk_score,
        relief_score=relief_score,
        themes=tuple(dict.fromkeys(matched_themes)),
    )


def evaluate_news_impact(
    ticker: str,
    macro_headlines: list[Headline],
    ticker_headlines: list[Headline],
    config: ScannerConfig,
) -> NewsImpact:
    combined = dedupe_headlines([*ticker_headlines, *macro_headlines])
    scored: list[ScoredHeadline] = []
    theme_counter: Counter[str] = Counter()

    for headline in combined:
        scored_item = score_headline(headline)
        if scored_item is None:
            continue
        scored.append(scored_item)
        for theme in scored_item.themes:
            theme_counter[theme] += 1

    scored.sort(
        key=lambda item: (item.risk_score + item.relief_score, -(item.headline.age_hours or 9999)),
        reverse=True,
    )

    risk_score = sum(item.risk_score for item in scored)
    relief_score = sum(item.relief_score for item in scored)
    net_risk_score = max(risk_score - relief_score, 0.0)

    if net_risk_score >= config.hard_event_risk_threshold:
        level: NewsLevel = "EXTREME"
        size_multiplier = 0.35
    elif net_risk_score >= config.elevated_event_risk_threshold:
        level = "HIGH"
        size_multiplier = 0.55
    elif net_risk_score >= 2.5:
        level = "MODERATE"
        size_multiplier = 0.8
    else:
        level = "LOW"
        size_multiplier = 1.0

    if relief_score >= max(2.0, risk_score * 0.9):
        stance: NewsStance = "RELIEF"
    elif net_risk_score >= 2.5:
        stance = "VOLATILE"
    else:
        stance = "NEUTRAL"

    matched_themes = [f"{theme} x{count}" for theme, count in theme_counter.most_common(4)]

    return NewsImpact(
        ticker=ticker,
        level=level,
        stance=stance,
        risk_score=risk_score,
        relief_score=relief_score,
        net_risk_score=net_risk_score,
        size_multiplier=size_multiplier,
        matched_themes=matched_themes,
        headlines=scored[:4],
        macro_count=len(macro_headlines),
        ticker_count=len(ticker_headlines),
    )


def neutral_news_impact(ticker: str) -> NewsImpact:
    return NewsImpact(
        ticker=ticker,
        level="LOW",
        stance="NEUTRAL",
        risk_score=0.0,
        relief_score=0.0,
        net_risk_score=0.0,
        size_multiplier=1.0,
        matched_themes=[],
        headlines=[],
        macro_count=0,
        ticker_count=0,
    )


def parse_calendar_earnings_date(value: object) -> calendar_date | None:
    if isinstance(value, list):
        for item in value:
            parsed = parse_calendar_earnings_date(item)
            if parsed is not None:
                return parsed
        return None
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, calendar_date):
        return value
    return None


def fetch_earnings_context(ticker: str, anchor_date: calendar_date) -> EarningsContext:
    next_earnings_date: calendar_date | None = None

    try:
        calendar = yf.Ticker(ticker).calendar
    except Exception:
        calendar = {}

    if isinstance(calendar, dict):
        next_earnings_date = parse_calendar_earnings_date(calendar.get("Earnings Date"))

    if next_earnings_date is None:
        return EarningsContext(
            next_earnings_date=None,
            days_to_earnings=None,
            label="data non disponibile",
            warning=None,
        )

    days_to_earnings = (next_earnings_date - anchor_date).days
    if days_to_earnings < 0:
        label = "gia passata"
        warning = None
    elif days_to_earnings == 0:
        label = "oggi"
        warning = "earnings oggi: evitare nuove aperture"
    elif days_to_earnings == 1:
        label = "domani"
        warning = "earnings domani: evitare nuove aperture"
    elif days_to_earnings <= 5:
        label = f"tra {days_to_earnings} giorni"
        warning = f"earnings tra {days_to_earnings} giorni: valutare size ridotta o uscita preventiva"
    else:
        label = f"tra {days_to_earnings} giorni"
        warning = None

    return EarningsContext(
        next_earnings_date=next_earnings_date,
        days_to_earnings=days_to_earnings,
        label=label,
        warning=warning,
    )


def analyze_market_context(config: ScannerConfig) -> tuple[MarketContext, pd.DataFrame, NewsImpact, list[Headline]]:
    benchmark_df = add_indicators(
        download_ohlcv(
            config.benchmark_ticker,
            period=config.daily_period,
            interval=config.daily_interval,
            max_retries=config.max_download_retries,
            retry_sleep_seconds=config.retry_sleep_seconds,
        ),
        config,
    )
    growth_df = add_indicators(
        download_ohlcv(
            config.growth_benchmark_ticker,
            period=config.daily_period,
            interval=config.daily_interval,
            max_retries=config.max_download_retries,
            retry_sleep_seconds=config.retry_sleep_seconds,
        ),
        config,
    )
    vix_df = download_ohlcv(
        config.volatility_ticker,
        period=config.daily_period,
        interval=config.daily_interval,
        max_retries=config.max_download_retries,
        retry_sleep_seconds=config.retry_sleep_seconds,
    ).copy()
    vix_window = effective_window(20, len(vix_df), minimum=10)
    vix_df["sma20"] = vix_df["Close"].rolling(vix_window, min_periods=vix_window).mean()

    validate_analysis_frame(benchmark_df, config.benchmark_ticker, config)
    validate_analysis_frame(growth_df, config.growth_benchmark_ticker, config)
    if len(vix_df) < 20 or pd.isna(vix_df.iloc[-1]["sma20"]):
        raise RuntimeError("Not enough VIX history to build market context.")

    benchmark_last = benchmark_df.iloc[-1]
    growth_last = growth_df.iloc[-1]
    vix_last = vix_df.iloc[-1]

    benchmark_trend = detect_trend(benchmark_df)
    growth_trend = detect_trend(growth_df)
    vix_close = float(vix_last["Close"])
    vix_sma20 = float(vix_last["sma20"])
    vix_month_return = trailing_return(vix_df["Close"], 21)

    warnings: list[str] = []
    if benchmark_trend != "UP":
        warnings.append("SPY is not in a confirmed uptrend")
    if growth_trend != "UP":
        warnings.append("QQQ is not in a confirmed uptrend")
    if vix_close >= config.vix_risk_off_floor:
        warnings.append(f"VIX is elevated at {vix_close:.2f}")
    elif vix_close > config.vix_risk_on_ceiling:
        warnings.append(f"VIX is above comfort zone at {vix_close:.2f}")

    if (
        (benchmark_trend == "DOWN" and growth_trend == "DOWN")
        or (vix_close >= config.vix_risk_off_floor and vix_month_return > 0)
    ):
        risk_mode: RiskMode = "RISK_OFF"
    elif benchmark_trend == "UP" and growth_trend == "UP" and vix_close <= config.vix_risk_on_ceiling:
        risk_mode = "RISK_ON"
    else:
        risk_mode = "MIXED"

    if config.news_enabled:
        macro_headlines = fetch_macro_headlines(config)
        macro_news = evaluate_news_impact("MARKET", macro_headlines, [], config)
    else:
        macro_headlines = []
        macro_news = neutral_news_impact("MARKET")

    context = MarketContext(
        benchmark_trend=benchmark_trend,
        growth_trend=growth_trend,
        benchmark_close=float(benchmark_last["Close"]),
        benchmark_sma50=float(benchmark_last["sma50"]),
        growth_close=float(growth_last["Close"]),
        growth_sma50=float(growth_last["sma50"]),
        vix_close=vix_close,
        vix_sma20=vix_sma20,
        risk_mode=risk_mode,
        warnings=warnings,
    )

    return context, benchmark_df, macro_news, macro_headlines

def build_technical_signal(
    daily: DailyAnalysis,
    df_daily: pd.DataFrame,
    config: ScannerConfig,
) -> tuple[Signal, float, list[str], list[str]]:
    last_daily = df_daily.iloc[-1]

    long_checks: list[tuple[str, bool]] = [
        ("daily trend up", daily.trend == "UP"),
        ("close above SMA50", pd.notna(last_daily["sma50"]) and last_daily["Close"] > last_daily["sma50"]),
        ("close above SMA200", pd.notna(last_daily["sma200"]) and last_daily["Close"] > last_daily["sma200"]),
        ("EMA alignment bullish", daily.ema_fast > daily.ema_slow),
        ("MACD above signal", daily.macd > daily.macd_signal),
        ("ADX above threshold", daily.adx >= config.min_adx),
        ("RSI in bullish range", 52 <= daily.rsi <= 72),
        ("relative strength positive vs SPY over 1M", daily.relative_strength_1m > 0),
        ("relative strength not weak vs SPY over 3M", daily.relative_strength_3m > -0.01),
        ("price near or above resistance", daily.breakout_ready),
        ("volume not weak", daily.volume_label != "Volume low"),
    ]
    short_checks: list[tuple[str, bool]] = [
        ("daily trend down", daily.trend == "DOWN"),
        ("close below SMA50", pd.notna(last_daily["sma50"]) and last_daily["Close"] < last_daily["sma50"]),
        ("close below SMA200", pd.notna(last_daily["sma200"]) and last_daily["Close"] < last_daily["sma200"]),
        ("EMA alignment bearish", daily.ema_fast < daily.ema_slow),
        ("MACD below signal", daily.macd < daily.macd_signal),
        ("ADX above threshold", daily.adx >= config.min_adx),
        ("RSI in bearish range", 28 <= daily.rsi <= 48),
        ("relative weakness vs SPY over 1M", daily.relative_strength_1m < 0),
        ("relative weakness vs SPY over 3M", daily.relative_strength_3m < 0.01),
        ("price near or below support", daily.breakdown_ready),
        ("volume not weak", daily.volume_label != "Volume low"),
    ]

    long_score = sum(ok for _, ok in long_checks)
    short_score = sum(ok for _, ok in short_checks)
    total_checks = len(long_checks)

    reasons: list[str] = []
    warnings: list[str] = []

    if long_score >= 9 and long_score >= short_score + 2:
        signal: Signal = "LONG"
        confidence = long_score / total_checks
        reasons = [label for label, ok in long_checks if ok]
    elif short_score >= 9 and short_score >= long_score + 2:
        signal = "SHORT"
        confidence = short_score / total_checks
        reasons = [label for label, ok in short_checks if ok]
    else:
        signal = "NO TRADE"
        confidence = max(long_score, short_score) / total_checks
        if long_score >= short_score:
            reasons = [f"missing for LONG: {label}" for label, ok in long_checks if not ok][:5]
        else:
            reasons = [f"missing for SHORT: {label}" for label, ok in short_checks if not ok][:5]

    if daily.divergence:
        warnings.append(daily.divergence)
    if daily.atr_pct < 0.015:
        warnings.append("daily volatility is compressed")
    if daily.volume_label == "Volume low":
        warnings.append("daily volume is below average")
    confidence = max(0.0, min(confidence, 0.99))
    return signal, confidence, reasons, warnings


def build_signal(
    technical_signal: Signal,
    technical_confidence: float,
    technical_reasons: list[str],
    technical_warnings: list[str],
    daily: DailyAnalysis,
    market: MarketContext,
    macro_news: NewsImpact,
    company_news: NewsImpact,
    earnings: EarningsContext,
    config: ScannerConfig,
) -> tuple[Signal, float, list[str], list[str]]:
    signal = technical_signal
    confidence = technical_confidence
    reasons = list(technical_reasons)
    warnings = list(technical_warnings)

    if market.warnings:
        warnings.extend(market.warnings[:2])
    if macro_news.matched_themes:
        warnings.append(f"macro themes: {', '.join(macro_news.matched_themes[:3])}")
    if company_news.matched_themes:
        warnings.append(f"company themes: {', '.join(company_news.matched_themes[:3])}")
    if earnings.warning:
        warnings.append(earnings.warning)

    if signal != "NO TRADE":
        if signal == "LONG":
            if market.risk_mode == "RISK_OFF":
                confidence *= 0.78
                warnings.append("macro regime risk-off: long aggressivi sconsigliati")
            elif market.risk_mode == "MIXED":
                confidence *= 0.92

            if macro_news.level == "HIGH":
                confidence *= 0.86
            elif macro_news.level == "EXTREME":
                if not (daily.breakout_ready and daily.adx >= config.min_adx + 5 and daily.volume_label == "Volume high"):
                    signal = "NO TRADE"
                    confidence = min(confidence, 0.5)
                    reasons = ["macro risk troppo elevato per aprire nuovi long"]
                    warnings.append("macro volatility extreme")
                else:
                    confidence *= 0.74

        elif signal == "SHORT":
            if market.risk_mode == "RISK_ON":
                confidence *= 0.8
                warnings.append("macro regime risk-on: short meno puliti")
            elif market.risk_mode == "MIXED":
                confidence *= 0.95

            if macro_news.stance == "RELIEF":
                confidence *= 0.86
                warnings.append("relief headlines can squeeze shorts")
            if macro_news.level == "HIGH":
                confidence *= 0.88
            elif macro_news.level == "EXTREME":
                if not (daily.breakdown_ready and daily.adx >= config.min_adx + 4):
                    signal = "NO TRADE"
                    confidence = min(confidence, 0.5)
                    reasons = ["macro risk troppo elevato per aprire nuovi short"]
                    warnings.append("macro volatility extreme")
                else:
                    confidence *= 0.78

        if company_news.level == "HIGH":
            confidence *= 0.9
            warnings.append("news aziendali rilevanti: size down")
        elif company_news.level == "EXTREME":
            signal = "NO TRADE"
            confidence = min(confidence, 0.5)
            reasons = ["news aziendali troppo impattanti per aprire un nuovo swing"]

        if earnings.days_to_earnings is not None:
            if 0 <= earnings.days_to_earnings <= 1:
                signal = "NO TRADE"
                confidence = min(confidence, 0.5)
                reasons = ["trimestrale troppo vicina: evitare nuove aperture"]
            elif 2 <= earnings.days_to_earnings <= 5:
                confidence *= 0.8
                reasons.append("trimestrale vicina: size ridotta o uscita preventiva")

        if signal != "NO TRADE":
            if macro_news.level in {"HIGH", "EXTREME"}:
                reasons.append("macro risk elevato: trade consentito solo con size ridotta")
            if company_news.level == "HIGH":
                reasons.append("news aziendali attive: monitorare gap risk")

    confidence = max(0.0, min(confidence, 0.99))
    return signal, confidence, reasons, warnings


def position_multiplier(
    signal: Signal,
    market: MarketContext,
    macro_news: NewsImpact,
    company_news: NewsImpact,
    earnings: EarningsContext,
) -> float:
    if signal == "NO TRADE":
        return 0.0

    multiplier = min(macro_news.size_multiplier, company_news.size_multiplier)

    if signal == "LONG":
        if market.risk_mode == "MIXED":
            multiplier *= 0.85
        elif market.risk_mode == "RISK_OFF":
            multiplier *= 0.55
    elif signal == "SHORT":
        if market.risk_mode == "MIXED":
            multiplier *= 0.95
        elif market.risk_mode == "RISK_ON":
            multiplier *= 0.75

    if earnings.days_to_earnings is not None and 2 <= earnings.days_to_earnings <= 5:
        multiplier *= 0.6

    return max(0.1, min(multiplier, 1.0))


def build_price_chart(df: pd.DataFrame, max_points: int) -> list[PriceChartPoint]:
    chart_slice = df.tail(max_points)
    points: list[PriceChartPoint] = []

    for index, row in chart_slice.iterrows():
        point_date = pd.Timestamp(index).date()
        points.append(
            PriceChartPoint(
                date=point_date,
                close=float(row["Close"]),
                sma50=safe_float(row.get("sma50")),
                sma200=safe_float(row.get("sma200")),
            )
        )

    return points


def choose_stop_level(
    signal: Signal,
    entry: float,
    atr_stop: float,
    structure_stop: float | None,
    atr: float,
    config: ScannerConfig,
) -> float:
    candidates = [atr_stop]

    if structure_stop is not None:
        if signal == "LONG":
            structure_risk = entry - structure_stop
        else:
            structure_risk = structure_stop - entry

        if atr > 0:
            min_structure_risk = atr * config.min_structure_stop_atr
            max_structure_risk = atr * config.max_structure_stop_atr
            if min_structure_risk <= structure_risk <= max_structure_risk:
                candidates.append(structure_stop)

    if signal == "LONG":
        valid = [level for level in candidates if level < entry]
        return max(valid) if valid else atr_stop

    valid = [level for level in candidates if level > entry]
    return min(valid) if valid else atr_stop


def calculate_risk_levels(
    signal: Signal,
    daily: DailyAnalysis,
    market: MarketContext,
    macro_news: NewsImpact,
    company_news: NewsImpact,
    earnings: EarningsContext,
    config: ScannerConfig,
) -> tuple[float | None, float | None, float | None, float | None, float | None, int | None, float]:
    if signal == "NO TRADE":
        return None, None, None, None, None, None, 0.0

    entry = daily.close
    atr = daily.atr

    if signal == "LONG":
        atr_stop = entry - atr * config.atr_multiplier
        structure_stop = (daily.support - atr * 0.2) if daily.support is not None else atr_stop
        stop = choose_stop_level(signal, entry, atr_stop, structure_stop, atr, config)
        risk = entry - stop
        target = entry + risk * config.rr_ratio
    else:
        atr_stop = entry + atr * config.atr_multiplier
        structure_stop = (daily.resistance + atr * 0.2) if daily.resistance is not None else atr_stop
        stop = choose_stop_level(signal, entry, atr_stop, structure_stop, atr, config)
        risk = stop - entry
        target = entry - risk * config.rr_ratio

    if risk <= 0:
        return None, None, None, None, None, None, 0.0

    max_risk_amount = config.account_size * config.risk_per_trade
    size_factor = position_multiplier(signal, market, macro_news, company_news, earnings)
    position_size = math.floor((max_risk_amount / risk) * size_factor)
    reward = abs(target - entry)

    return entry, stop, target, risk, reward, position_size, size_factor


def grade_signal(
    signal: Signal,
    confidence: float,
    macro_news: NewsImpact,
    company_news: NewsImpact,
    earnings: EarningsContext,
) -> str:
    if signal == "NO TRADE":
        return "-"
    if earnings.days_to_earnings is not None and 0 <= earnings.days_to_earnings <= 5:
        return "C"
    if confidence >= 0.9 and macro_news.level in {"LOW", "MODERATE"} and company_news.level in {"LOW", "MODERATE"}:
        return "A"
    if confidence >= 0.78:
        return "B"
    return "C"


def build_commentary(setup: TradeSetup) -> str:
    return (
        f"Tecnico {setup.technical_signal} ({setup.technical_confidence:.0%}), "
        f"operativo {setup.signal} ({setup.confidence:.0%}). "
        f"Trend {setup.daily.trend}, RSI {setup.daily.rsi:.1f}, ADX {setup.daily.adx:.1f}, "
        f"macro {setup.market.risk_mode} / {setup.macro_news.level.lower()}, "
        f"news azienda {setup.company_news.level.lower()}, "
        f"trimestrale {setup.earnings.label}."
    )


def scan_ticker(
    ticker: str,
    benchmark_df: pd.DataFrame,
    market: MarketContext,
    macro_news: NewsImpact,
    macro_headlines: list[Headline],
    config: ScannerConfig,
) -> TradeSetup:
    df_daily = add_indicators(
        download_ohlcv(
            ticker,
            period=config.daily_period,
            interval=config.daily_interval,
            max_retries=config.max_download_retries,
            retry_sleep_seconds=config.retry_sleep_seconds,
        ),
        config,
    )

    validate_analysis_frame(df_daily, ticker, config)

    anchor_date = pd.Timestamp(df_daily.index[-1]).date()
    if config.news_enabled:
        ticker_headlines = fetch_ticker_headlines(ticker, config)
        company_news = evaluate_news_impact(ticker, [], ticker_headlines, config)
    else:
        ticker_headlines = []
        company_news = neutral_news_impact(ticker)
    daily = analyze_daily(df_daily, benchmark_df, config)
    price_chart = build_price_chart(df_daily, config.chart_points)
    earnings = fetch_earnings_context(ticker, anchor_date)
    technical_signal, technical_confidence, technical_reasons, technical_warnings = build_technical_signal(daily, df_daily, config)
    signal, confidence, reasons, warnings = build_signal(
        technical_signal,
        technical_confidence,
        technical_reasons,
        technical_warnings,
        daily,
        market,
        macro_news,
        company_news,
        earnings,
        config,
    )
    entry, stop, target, risk, reward, shares, size_factor = calculate_risk_levels(
        signal,
        daily,
        market,
        macro_news,
        company_news,
        earnings,
        config,
    )

    setup = TradeSetup(
        ticker=ticker,
        analysis_date=anchor_date,
        signal=signal,
        confidence=confidence,
        technical_signal=technical_signal,
        technical_confidence=technical_confidence,
        grade=grade_signal(signal, confidence, macro_news, company_news, earnings),
        entry=entry,
        stop=stop,
        target=target,
        risk_per_share=risk,
        reward_per_share=reward,
        position_size=shares,
        position_multiplier=size_factor,
        daily=daily,
        market=market,
        macro_news=macro_news,
        company_news=company_news,
        earnings=earnings,
        price_chart=price_chart,
        technical_reasons=technical_reasons,
        technical_warnings=technical_warnings,
        reasons=reasons,
        warnings=warnings,
    )
    setup.commentary = build_commentary(setup)
    return setup


def format_price(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2%}"


def format_move_pct(entry: float | None, level: float | None) -> str:
    if entry is None or level is None or entry == 0:
        return "n/a"
    pct = abs(float(level) - float(entry)) / abs(float(entry))
    return f"{pct:.2%}"


def signal_label(signal: Signal) -> str:
    return {
        "LONG": "LONG",
        "SHORT": "SHORT",
        "NO TRADE": "NO TRADE",
    }[signal]


def compact_list(items: list[str], limit: int = 3, fallback: str = "-") -> str:
    cleaned = [item.strip() for item in items if item and item.strip()]
    if not cleaned:
        return fallback
    return " | ".join(cleaned[:limit])


def build_console_summary_frame(setups: list[TradeSetup]) -> pd.DataFrame:
    rows = []
    for setup in setups:
        rows.append(
            {
                "Ticker": setup.ticker,
                "Tecnico": signal_label(setup.technical_signal),
                "Operativo": signal_label(setup.signal),
                "ConfTec": f"{setup.technical_confidence:.0%}",
                "ConfOp": f"{setup.confidence:.0%}",
                "Trend": setup.daily.trend,
                "Mercato": setup.market.risk_mode,
                "Macro": f"{setup.macro_news.level} ({setup.macro_news.net_risk_score:.1f})",
                "Azienda": f"{setup.company_news.level} ({setup.company_news.net_risk_score:.1f})",
                "Earnings": setup.earnings.label,
                "RSI": f"{setup.daily.rsi:.1f}",
                "ADX": f"{setup.daily.adx:.1f}",
                "RS1M": format_pct(setup.daily.relative_strength_1m),
                "Entry": format_price(setup.entry),
                "Stop": format_price(setup.stop),
                "Target": format_price(setup.target),
                "Size": str(setup.position_size) if setup.position_size else "-",
            }
        )
    return pd.DataFrame(rows)


def print_scan_overview(setups: list[TradeSetup]) -> None:
    longs = [setup.ticker for setup in setups if setup.signal == "LONG"]
    shorts = [setup.ticker for setup in setups if setup.signal == "SHORT"]
    blocked = [setup.ticker for setup in setups if setup.signal == "NO TRADE"]

    print("\n=== PANORAMICA ===")
    print(
        f"LONG: {len(longs)} | SHORT: {len(shorts)} | NO TRADE: {len(blocked)}"
    )
    if longs:
        print("Long candidati:", ", ".join(longs))
    if shorts:
        print("Short candidati:", ", ".join(shorts))
    if not longs and not shorts:
        print("Nessun setup operativo pulito nelle condizioni attuali.")


def print_market_context(context: MarketContext, macro_news: NewsImpact) -> None:
    print("\n=== CONTESTO MERCATO ===")
    print(
        f"Regime: {context.risk_mode} | SPY: {context.benchmark_trend} | "
        f"QQQ: {context.growth_trend} | VIX: {context.vix_close:.2f} "
        f"(SMA20 {context.vix_sma20:.2f})"
    )
    print(
        f"Rischio macro-news: {macro_news.level} ({macro_news.net_risk_score:.1f}) | "
        f"Temi: {compact_list(macro_news.matched_themes, limit=4)}"
    )
    if context.warnings:
        print("Warning:", compact_list(context.warnings, limit=3))
    if macro_news.headlines:
        print("Headline macro chiave:")
        for index, item in enumerate(macro_news.headlines[:2], start=1):
            print(f"{index}. [{item.headline.source}] {item.headline.title}")


def print_setup(setup: TradeSetup) -> None:
    operational_notes = [reason for reason in setup.reasons if reason not in setup.technical_reasons]
    if not operational_notes:
        operational_notes = setup.reasons

    print(f"\n=== {setup.ticker} ===")
    print(
        f"Decisione operativa: {signal_label(setup.signal)} | Grade {setup.grade} | Confidenza {setup.confidence:.0%}"
    )
    print(
        f"Analisi tecnica: {signal_label(setup.technical_signal)} | Confidenza tecnica {setup.technical_confidence:.0%}"
    )
    print(
        f"Trend {setup.daily.trend} | RSI {setup.daily.rsi:.1f} | ADX {setup.daily.adx:.1f} | "
        f"ATR {setup.daily.atr:.2f} | RS1M vs SPY {format_pct(setup.daily.relative_strength_1m)}"
    )
    print(
        f"Analisi macro: Mercato {setup.market.risk_mode} | Macro-news {setup.macro_news.level} ({setup.macro_news.net_risk_score:.1f}) | "
        f"News azienda {setup.company_news.level} ({setup.company_news.net_risk_score:.1f})"
    )
    print(
        f"Trimestrale: {setup.earnings.next_earnings_date or 'n/d'} | Stato: {setup.earnings.label} | Size x{setup.position_multiplier:.2f}"
    )
    if setup.signal != "NO TRADE":
        print(
            f"Entry {format_price(setup.entry)} | Stop {format_price(setup.stop)} | "
            f"Target {format_price(setup.target)} | Size {setup.position_size}"
        )
        print(
            f"Rischio/azione {format_price(setup.risk_per_share)} | "
            f"Reward/azione {format_price(setup.reward_per_share)} | "
            f"Perdita potenziale {format_move_pct(setup.entry, setup.stop)} | "
            f"Guadagno potenziale {format_move_pct(setup.entry, setup.target)}"
        )
    print(
        "Conferme tecniche:"
        if setup.technical_signal != "NO TRADE"
        else "Limiti tecnici:",
        compact_list(setup.technical_reasons, limit=4),
    )
    print(
        "Decisione operativa:"
        if setup.signal != "NO TRADE"
        else "Blocco principale:",
        compact_list(operational_notes, limit=4),
    )
    print("Temi macro:", compact_list(setup.macro_news.matched_themes, limit=3))
    print("Temi azienda:", compact_list(setup.company_news.matched_themes, limit=3))
    print("Warning:", compact_list(setup.warnings, limit=3, fallback="nessuno"))
    if setup.macro_news.headlines:
        print("Headline macro:")
        for index, item in enumerate(setup.macro_news.headlines[:2], start=1):
            print(f"{index}. [{item.headline.source}] {item.headline.title}")
    if setup.company_news.headlines:
        print("Headline azienda:")
        for index, item in enumerate(setup.company_news.headlines[:2], start=1):
            print(f"{index}. [{item.headline.source}] {item.headline.title}")
    print("Sintesi:", setup.commentary)


def build_summary_frame(setups: list[TradeSetup]) -> pd.DataFrame:
    rows = []
    for setup in setups:
        rows.append(
            {
                "Ticker": setup.ticker,
                "AnalysisDate": setup.analysis_date,
                "Signal": setup.signal,
                "TechnicalSignal": setup.technical_signal,
                "Grade": setup.grade,
                "ConfidencePct": round(setup.confidence * 100, 1),
                "TechnicalConfidencePct": round(setup.technical_confidence * 100, 1),
                "TrendDaily": setup.daily.trend,
                "MarketMode": setup.market.risk_mode,
                "MacroNewsLevel": setup.macro_news.level,
                "MacroNewsScore": round(setup.macro_news.net_risk_score, 2),
                "MacroThemes": ", ".join(setup.macro_news.matched_themes[:3]),
                "CompanyNewsLevel": setup.company_news.level,
                "CompanyNewsScore": round(setup.company_news.net_risk_score, 2),
                "CompanyThemes": ", ".join(setup.company_news.matched_themes[:3]),
                "NextEarningsDate": setup.earnings.next_earnings_date,
                "DaysToEarnings": setup.earnings.days_to_earnings,
                "Entry": setup.entry,
                "Stop": setup.stop,
                "Target": setup.target,
                "RiskPerShare": setup.risk_per_share,
                "PositionSize": setup.position_size,
                "SizeMultiplier": round(setup.position_multiplier, 2),
                "DailyRSI": round(setup.daily.rsi, 2),
                "DailyADX": round(setup.daily.adx, 2),
                "DailyATR": round(setup.daily.atr, 2),
                "RS1MvsSPY": round(setup.daily.relative_strength_1m * 100, 2),
            }
        )

    summary = pd.DataFrame(rows)
    signal_rank = {"LONG": 0, "SHORT": 1, "NO TRADE": 2}
    summary["SignalRank"] = summary["Signal"].map(signal_rank)
    summary = summary.sort_values(["SignalRank", "ConfidencePct", "Ticker"], ascending=[True, False, True])
    return summary.drop(columns=["SignalRank"]).reset_index(drop=True)


def run_scan(
    config: ScannerConfig,
) -> tuple[MarketContext, NewsImpact, list[TradeSetup], list[str], pd.DataFrame]:
    market_context, benchmark_df, macro_news, macro_headlines = analyze_market_context(config)

    setups_by_index: dict[int, TradeSetup] = {}
    failures_by_index: dict[int, str] = {}
    worker_count = max(1, min(config.scan_workers, len(config.tickers)))

    if worker_count == 1:
        for index, ticker in enumerate(config.tickers):
            try:
                setup = scan_ticker(ticker, benchmark_df, market_context, macro_news, macro_headlines, config)
                setups_by_index[index] = setup
            except Exception as exc:
                failures_by_index[index] = f"{ticker}: {exc}"
    else:
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="scan") as executor:
            future_map = {
                executor.submit(scan_ticker, ticker, benchmark_df, market_context, macro_news, macro_headlines, config): (index, ticker)
                for index, ticker in enumerate(config.tickers)
            }

            for future in as_completed(future_map):
                index, ticker = future_map[future]
                try:
                    setups_by_index[index] = future.result()
                except Exception as exc:
                    failures_by_index[index] = f"{ticker}: {exc}"

    setups = [setups_by_index[index] for index in sorted(setups_by_index)]
    failures = [failures_by_index[index] for index in sorted(failures_by_index)]

    summary = build_summary_frame(setups) if setups else pd.DataFrame()
    return market_context, macro_news, setups, failures, summary


def main() -> None:
    args = parse_args()
    config = ScannerConfig(
        tickers=tuple(args.tickers),
        daily_period=args.daily_period,
        account_size=args.account_size,
        risk_per_trade=args.risk_per_trade,
        news_lookback_days=args.news_lookback_days,
        news_enabled=args.enable_news,
    )

    print(f"\n=== DAILY SWING AI SCAN | {datetime.now().isoformat(sep=' ', timespec='seconds')} ===")
    print(f"Tickers: {', '.join(config.tickers)}")
    print(
        f"Daily data: {config.daily_period} / {config.daily_interval} | "
        f"News: {'ON' if config.news_enabled else 'OFF'} | "
        f"Macro news lookback: {config.news_lookback_days}d"
    )

    market_context, macro_news, setups, failures, summary = run_scan(config)
    print_market_context(market_context, macro_news)
    for setup in setups:
        print_setup(setup)

    if setups:
        console_summary = build_console_summary_frame(setups)
        print_scan_overview(setups)
        print("\n=== TABELLA FINALE ===")
        print(console_summary.to_string(index=False))
        if args.export_csv:
            summary.to_csv(args.export_csv, index=False)
            print(f"\nCSV esportato in {args.export_csv}")

    if failures:
        print("\n=== ERRORI ===")
        for item in failures:
            print(f"- {item}")


if __name__ == "__main__":
    main()
