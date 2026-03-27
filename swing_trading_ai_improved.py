from __future__ import annotations

from swing_trading import (
    DEFAULT_TICKERS,
    TOP_100_US_TICKERS,
    ScannerConfig,
    build_console_summary_frame,
    format_pct,
    format_price,
    run_scan_legacy,
)


def run_scan(config: ScannerConfig):
    return run_scan_legacy(config)


if __name__ == "__main__":
    config = ScannerConfig(tickers=DEFAULT_TICKERS)
    market_context, _macro_news, setups, failures, _summary = run_scan(config)
    print("=== SWING TRADING AI ===")
    print(f"Regime: {market_context.risk_mode}")
    if setups:
        print(build_console_summary_frame(setups).to_string(index=False))
    if failures:
        print("Failures:")
        for item in failures:
            print(f"- {item}")
