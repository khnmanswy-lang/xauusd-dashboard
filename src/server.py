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

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.config.settings import settings
from src.core.risk_calculator import calculate_lot_size
from src.integrations.market_data import MarketDataEngine
from src.integrations.macro_feed import MacroFeed
from src.integrations.economic_calendar import EconomicCalendar
from src.integrations.ai_client import AiClient
from src.integrations.oanda_client import OandaClient
from src.core.ai_analyzer import AiSetupAnalyzer
from src.core.trade_journal import TradeJournalManager, JournalEntry
from src.core.auto_trader import AutoTrader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("server")

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

# Singleton engine instances
macro_feed = MacroFeed(poll_interval=settings.macro.poll_interval_seconds)
economic_calendar = EconomicCalendar()
market_engine = MarketDataEngine(macro_feed=macro_feed, calendar=economic_calendar)
ai_client = AiClient()
ai_analyzer = AiSetupAnalyzer(market_engine=market_engine, ai_client=ai_client)
trade_journal = TradeJournalManager()
oanda_client = OandaClient(settings.oanda)
auto_trader = AutoTrader(
    market_engine=market_engine,
    ai_analyzer=ai_analyzer,
    oanda_client=oanda_client,
    trade_journal=trade_journal,
    enabled=True
)
scheduler = AsyncIOScheduler()


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


# Cached active position state
_current_active_position: Optional[Dict[str, Any]] = None


async def get_active_oanda_position() -> Optional[Dict[str, Any]]:
    """Helper to query and format active open trade on OANDA."""
    global _current_active_position
    if not oanda_client.is_configured():
        return None
    try:
        open_trades = await oanda_client.get_open_trades()
        if open_trades:
            ot = open_trades[0]
            units_val = float(ot.get("currentUnits", 0))
            _current_active_position = {
                "id": ot.get("id"),
                "instrument": ot.get("instrument", "XAU_USD"),
                "direction": "BULLISH_LONG" if units_val > 0 else "BEARISH_SHORT",
                "units": units_val,
                "entry_price": float(ot.get("price", 0.0)),
                "stop_loss": float(ot.get("stopLossOrder", {}).get("price", 0.0)) if ot.get("stopLossOrder") else None,
                "take_profit": float(ot.get("takeProfitOrder", {}).get("price", 0.0)) if ot.get("takeProfitOrder") else None,
                "unrealized_pl": float(ot.get("unrealizedPL", 0.0)),
                "open_time": ot.get("openTime")
            }
        else:
            _current_active_position = None
    except Exception as e:
        logger.debug("Error fetching open OANDA trades: %s", e)
    return _current_active_position


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown routines."""
    logger.info("Starting XAUUSD Dashboard engine...")
    await market_engine.start()

    # Wire market engine listener to WebSocket manager
    async def _on_market_update(state: Dict[str, Any]):
        state["active_trade"] = _current_active_position
        await manager.broadcast(state)

    # Wire AI analyzer listener to WebSocket manager
    async def _on_ai_update(payload: Dict[str, Any]):
        await manager.broadcast(payload)

    market_engine.add_listener(_on_market_update)
    ai_analyzer.add_listener(_on_ai_update)

    # Combined 60-second cron runner: evaluates market setups & runs auto-trader sentry
    async def _scheduled_cron_pass():
        try:
            await ai_analyzer.evaluate_market()
            trade_res = await auto_trader.evaluate_and_trade()
            await get_active_oanda_position()
            if trade_res.get("status") in ["EXECUTED", "TRAILING_UPDATED", "ADR_EXHAUSTED"]:
                await manager.broadcast({
                    "type": "AUTO_TRADE_UPDATE",
                    "data": trade_res
                })
        except Exception as e:
            logger.error("Error during scheduled cron pass: %s", e)

    # Run initial evaluation
    try:
        await _scheduled_cron_pass()
    except Exception as e:
        logger.debug("Initial evaluation pass: %s", e)

    # Start 60-second background cron scanner
    scheduler.add_job(
        _scheduled_cron_pass,
        trigger="interval",
        seconds=settings.ai.scanner_interval_seconds,
        id="ai_market_evaluator",
        replace_existing=True
    )
    scheduler.start()
    logger.info("APScheduler started: AI market evaluation and AutoTrader running every %ds.", settings.ai.scanner_interval_seconds)

    yield

    logger.info("Shutting down XAUUSD Dashboard engine & scheduler...")
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass
    ai_analyzer.remove_listener(_on_ai_update)
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
    """Returns a full real-time state snapshot including latest AI trade plan."""
    frame = market_engine.get_state_frame()
    frame["ai_analysis"] = ai_analyzer.get_latest_analysis()
    frame["active_trade"] = await get_active_oanda_position()
    return frame


@app.get("/api/ai/latest")
async def get_ai_latest() -> Dict[str, Any]:
    """Returns the latest AI trade setup analysis and reasoning card."""
    return ai_analyzer.get_latest_analysis()


@app.post("/api/ai/analyze")
async def post_trigger_ai_analysis() -> Dict[str, Any]:
    """Triggers an immediate on-demand market evaluation pass and broadcasts the result."""
    return await ai_analyzer.evaluate_market()


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


@app.get("/api/journal/list")
async def get_journal_list(limit: int = Query(default=100, ge=1, le=500)) -> List[Dict[str, Any]]:
    """Returns a list of recorded trade journal entries."""
    return trade_journal.get_entries(limit=limit)


@app.get("/api/journal/export")
async def get_journal_export():
    """Exports trade journal history as a formatted downloadable CSV file."""
    csv_content = trade_journal.export_csv_string()
    from datetime import datetime, timezone
    filename = f"xauusd_trade_journal_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/api/journal/record")
async def post_record_trade(entry_data: Dict[str, Any]) -> Dict[str, Any]:
    """Records a trade setup or executed trade into the journal."""
    entry = trade_journal.add_entry(entry_data)
    return {"status": "success", "entry": entry.to_dict()}


@app.get("/api/autotrader/status")
async def get_autotrader_status() -> Dict[str, Any]:
    """Returns the current state and metrics of the AutoTrader sentry."""
    return {
        "enabled": auto_trader.enabled,
        "oanda_configured": oanda_client.is_configured(),
        "last_trade_time": auto_trader.last_trade_time,
        "risk_per_trade_pct": auto_trader.risk_per_trade_pct,
        "cooldown_seconds": auto_trader.cooldown_seconds
    }


@app.post("/api/autotrader/toggle")
async def post_autotrader_toggle(enabled: Optional[bool] = None) -> Dict[str, Any]:
    """Toggles or explicitly sets AutoTrader execution state."""
    new_state = auto_trader.toggle(enabled)
    return {"status": "success", "enabled": new_state}


# WebSocket Stream Route
@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """Low-latency WebSocket endpoint streaming continuous tick, state, and AI updates."""
    await manager.connect(websocket)
    try:
        # Send initial snapshot immediately upon connection (including AI analysis card)
        initial_state = market_engine.get_state_frame()
        initial_state["ai_analysis"] = ai_analyzer.get_latest_analysis()
        await websocket.send_text(json.dumps(initial_state))

        # Keep listening for incoming client messages (e.g. ping or on-demand re-scan request)
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif data == "request_ai_analysis":
                analysis = await ai_analyzer.evaluate_market()
                await websocket.send_text(json.dumps({
                    "type": "AI_ANALYSIS_UPDATE",
                    "data": analysis
                }))
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
