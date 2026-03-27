from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .constants import DEFAULT_DB_PATH, DEFAULT_TICKERS, DEFAULT_USER_ID
from .service import run_pipeline
from .storage import SQLiteStore

APP_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = APP_DIR / "static"


class WatchlistRequest(BaseModel):
    tickers: list[str] = Field(default_factory=lambda: list(DEFAULT_TICKERS))
    daily_period: str = "2y"


class SettingsRequest(BaseModel):
    theme: str = "system"
    density: str = "comfortable"
    default_view: str = "overview"
    favorite_metric: str = "confidence"
    show_only_actionable: bool = False


class RefreshRequest(BaseModel):
    tickers: list[str] | None = None
    daily_period: str = "2y"


def build_app() -> FastAPI:
    store = SQLiteStore(DEFAULT_DB_PATH)
    store.ensure_schema()
    store.seed_defaults()

    app = FastAPI(title="Swing Trading AI Refactored")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/api/dashboard")
    def dashboard() -> dict[str, Any]:
        return store.build_dashboard_bundle(user_id=DEFAULT_USER_ID)

    @app.get("/api/watchlist")
    def watchlist() -> dict[str, Any]:
        return {
            "tickers": store.list_active_tickers(),
            "settings": store.get_ui_preferences(),
        }

    @app.post("/api/watchlist")
    def update_watchlist(request: WatchlistRequest) -> dict[str, Any]:
        normalized = [ticker.strip().upper() for ticker in request.tickers if ticker.strip()]
        if not normalized:
            raise HTTPException(status_code=400, detail="At least one ticker is required.")
        store.replace_watchlist(normalized)
        result = run_pipeline(tickers=normalized, daily_period=request.daily_period)
        return {
            "message": "Watchlist updated and pipeline refreshed.",
            "tickers": normalized,
            "run_id": result["run_id"],
            "failures": result["failures"],
        }

    @app.get("/api/tickers/{ticker}")
    def ticker_detail(ticker: str) -> dict[str, Any]:
        payload = store.get_ticker_detail(ticker.strip().upper())
        if not payload.get("latest_prediction"):
            raise HTTPException(status_code=404, detail="Ticker not found in stored history.")
        return payload

    @app.get("/api/history")
    def history() -> dict[str, Any]:
        bundle = store.build_dashboard_bundle()
        return {
            "generated_at": bundle["generated_at"],
            "history": bundle["history"],
        }

    @app.get("/api/settings")
    def settings() -> dict[str, Any]:
        return store.get_ui_preferences()

    @app.put("/api/settings")
    def update_settings(request: SettingsRequest) -> dict[str, Any]:
        return store.save_ui_preferences(request.model_dump())

    @app.post("/api/refresh")
    def refresh(request: RefreshRequest) -> dict[str, Any]:
        result = run_pipeline(tickers=request.tickers, daily_period=request.daily_period)
        return {
            "message": "Daily refresh completed.",
            "run_id": result["run_id"],
            "saved_tickers": result["saved_tickers"],
            "failures": result["failures"],
        }

    @app.post("/api/scan")
    def scan(request: WatchlistRequest) -> dict[str, Any]:
        result = run_pipeline(tickers=request.tickers, daily_period=request.daily_period)
        return result["bundle"]

    @app.get("/api/defaults")
    def defaults() -> dict[str, Any]:
        return {
            "tickers": list(DEFAULT_TICKERS),
            "daily_period": "2y",
            "database_path": DEFAULT_DB_PATH,
            "static_export_path": "static/data/app-state.json",
        }

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = build_app()
