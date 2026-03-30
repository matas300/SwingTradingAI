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
from .validation import normalize_ticker_list

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
    risk_budget_pct: float = 0.01
    max_add_fraction: float = 0.25


class RefreshRequest(BaseModel):
    tickers: list[str] | None = None
    daily_period: str = "2y"


class OpenPositionFromSignalRequest(BaseModel):
    signal_id: str
    execution_price: float
    quantity: float
    executed_at: str
    fees: float = 0.0
    notes: str = ""


class PositionEventRequest(BaseModel):
    event_type: str
    quantity: float = 0.0
    price: float | None = None
    fees: float = 0.0
    executed_at: str | None = None
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_app() -> FastAPI:
    repository = SQLiteStore(DEFAULT_DB_PATH)
    repository.ensure_schema()
    repository.seed_defaults()

    app = FastAPI(title="SwingTradingAI")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/api/dashboard")
    def dashboard() -> dict[str, Any]:
        bundle = repository.build_dashboard_bundle(user_id=DEFAULT_USER_ID)
        bundle["capabilities"] = {
            "mode": "local-api",
            "write": True,
            "refresh": True,
            "auth_mode": "none",
        }
        return bundle

    @app.get("/api/watchlist")
    def watchlist() -> dict[str, Any]:
        return {
            "tickers": repository.list_active_tickers(DEFAULT_USER_ID),
            "settings": repository.get_ui_preferences(DEFAULT_USER_ID),
        }

    @app.post("/api/watchlist")
    def update_watchlist(request: WatchlistRequest) -> dict[str, Any]:
        try:
            normalized = normalize_ticker_list(request.tickers)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not normalized:
            raise HTTPException(status_code=400, detail="At least one ticker is required.")
        result = run_pipeline(tickers=normalized, daily_period=request.daily_period)
        return {
            "message": "Watchlist updated and pipeline refreshed.",
            "tickers": normalized,
            "run_id": result["run_id"],
            "failures": result["failures"],
        }

    @app.get("/api/tickers/{ticker}")
    def ticker_detail(ticker: str) -> dict[str, Any]:
        try:
            payload = repository.get_ticker_detail(ticker.strip().upper())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not payload.get("latest_prediction"):
            raise HTTPException(status_code=404, detail="Ticker not found in stored history.")
        return payload

    @app.get("/api/positions")
    def positions() -> dict[str, Any]:
        return {"items": repository.list_open_positions(DEFAULT_USER_ID)}

    @app.get("/api/positions/{position_id}")
    def position_detail(position_id: str) -> dict[str, Any]:
        try:
            return repository.get_position_detail(position_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/positions/from-signal")
    def open_position_from_signal(request: OpenPositionFromSignalRequest) -> dict[str, Any]:
        try:
            return repository.create_position_from_signal(
                signal_id=request.signal_id,
                execution_price=request.execution_price,
                quantity=request.quantity,
                executed_at=request.executed_at,
                fees=request.fees,
                notes=request.notes,
                user_id=DEFAULT_USER_ID,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/positions/{position_id}/events")
    def append_position_event(position_id: str, request: PositionEventRequest) -> dict[str, Any]:
        try:
            return repository.add_position_event(
                position_id=position_id,
                event_type=request.event_type,
                quantity=request.quantity,
                price=request.price,
                fees=request.fees,
                executed_at=request.executed_at,
                notes=request.notes,
                metadata=request.metadata,
                source="user",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/settings")
    def settings() -> dict[str, Any]:
        return repository.get_ui_preferences(DEFAULT_USER_ID)

    @app.put("/api/settings")
    def update_settings(request: SettingsRequest) -> dict[str, Any]:
        return repository.save_ui_preferences(request.model_dump(), DEFAULT_USER_ID)

    @app.post("/api/refresh")
    def refresh(request: RefreshRequest) -> dict[str, Any]:
        result = run_pipeline(tickers=request.tickers, daily_period=request.daily_period)
        return {
            "message": "Daily refresh completed.",
            "run_id": result["run_id"],
            "saved_tickers": result["saved_tickers"],
            "failures": result["failures"],
        }

    @app.get("/api/defaults")
    def defaults() -> dict[str, Any]:
        return {
            "tickers": list(DEFAULT_TICKERS),
            "daily_period": "2y",
            "database_path": DEFAULT_DB_PATH,
            "static_export_path": "static/data/app-state.json",
            "architecture": "Netlify + Firestore + GitHub Actions",
        }

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = build_app()
