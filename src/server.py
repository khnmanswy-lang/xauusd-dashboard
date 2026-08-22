"""
FastAPI Server & Real-Time WebSocket Broadcaster for XAUUSD Dashboard.
Serves static assets, REST analysis endpoints, and streams live multi-TF market state over WebSockets.
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Set, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.config.settings import settings
from src.core.risk_calculator import calculate_lot_size
from src.integrations.market_data import MarketDataEngine
from src.integrations.macro_feed import MacroFeed
from src.integrations.economic_calendar import EconomicCalendar

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("server")

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

# Singleton engine instances
macro_feed = MacroFeed(poll_interval=settings.macro.poll_interval_seconds)
economic_calendar = EconomicCalendar()
market_engine = MarketDataEngine(macro_feed=macro_feed, calendar=economic_calendar)


class ConnectionManager:
    """Manages active dashboard WebSocket connections and broadcasting."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info("Client connected. Total clients: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info("Client disconnected. Remaining clients: %d", len(self.active_connections))

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active_connections:
            return

        payload = json.dumps(message)
        dead_connections = set()

        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.add(connection)

        for dead in dead_connections:
            self.active_connections.discard(dead)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown routines."""
    logger.info("Starting XAUUSD Dashboard engine...")
    await market_engine.start()

    # Wire market engine listener to WebSocket manager
    async def _on_market_update(state: Dict[str, Any]):
        await manager.broadcast(state)

    market_engine.add_listener(_on_market_update)

    yield

    logger.info("Shutting down XAUUSD Dashboard engine...")
    market_engine.remove_listener(_on_market_update)
    await market_engine.stop()


app = FastAPI(
    title="Real-Time XAUUSD Multi-Timeframe Terminal",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Risk calculation request model
class RiskCalculateRequest(BaseModel):
    account_balance: float = 10000.0
    risk_percentage: float = 1.0
    atr_m5: Optional[float] = None
    sl_multiplier: float = 1.5
    custom_sl_distance: Optional[float] = None
    current_price: Optional[float] = None


# REST Routes
@app.get("/api/state")
async def get_state() -> Dict[str, Any]:
    """Returns a full real-time state snapshot."""
    return market_engine.get_state_frame()


@app.get("/api/history/{timeframe}")
async def get_history(timeframe: str) -> List[Dict[str, Any]]:
    """Returns historical OHLCV candles for a given timeframe (H1, M15, M5, M1)."""
    return market_engine.get_history(timeframe)


@app.get("/api/news")
async def get_news(limit: int = Query(default=5, ge=1, le=20)) -> List[Dict[str, Any]]:
    """Returns upcoming high-impact economic news releases."""
    return economic_calendar.get_upcoming_events(limit=limit)


@app.post("/api/risk/calculate")
async def post_calculate_risk(req: RiskCalculateRequest) -> Dict[str, Any]:
    """Calculates ATR-based dynamic lot sizing."""
    current_atr = req.atr_m5 or market_engine._volatility_state.get("atr_m5", 1.90)
    current_p = req.current_price or market_engine._current_price
    
    result = calculate_lot_size(
        account_balance=req.account_balance,
        risk_pct=req.risk_percentage,
        atr_m5=current_atr,
        sl_multiplier=req.sl_multiplier,
        custom_sl_distance=req.custom_sl_distance,
        current_price=current_p
    )
    return result.to_dict()


# WebSocket Stream Route
@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """Low-latency WebSocket endpoint streaming continuous tick and state updates."""
    await manager.connect(websocket)
    try:
        # Send initial snapshot immediately upon connection
        initial_state = market_engine.get_state_frame()
        await websocket.send_text(json.dumps(initial_state))

        # Keep listening for incoming client messages (e.g. ping or client settings)
        while True:
            data = await websocket.receive_text()
            # Handle client heartbeats or custom client commands if needed
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.debug("WebSocket exception: %s", e)
        manager.disconnect(websocket)


# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_index():
    """Serve main terminal index.html dashboard."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse(
        status_code=200,
        content={"status": "XAUUSD Dashboard Server Online", "ws_endpoint": "/ws/stream"}
    )
