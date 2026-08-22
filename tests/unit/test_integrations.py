"""
Unit tests for Integrations (market_data.py, macro_feed.py, economic_calendar.py).
"""
import pytest
import asyncio
from datetime import datetime, timezone
from src.integrations.macro_feed import MacroFeed, MacroItem
from src.integrations.economic_calendar import EconomicCalendar, NewsEvent
from src.integrations.market_data import MarketDataEngine


@pytest.mark.asyncio
async def test_macro_feed_snapshot():
    feed = MacroFeed()
    state = feed.get_state()
    assert "dxy" in state
    assert "us10y" in state
    assert state["dxy"]["symbol"] == "DXY"
    assert state["us10y"]["symbol"] == "US10Y"
    
    # Test fetch_macro_snapshot fallback
    snapshot = await feed.fetch_macro_snapshot()
    assert snapshot["dxy"]["price"] > 0
    assert snapshot["us10y"]["price"] > 0


def test_economic_calendar():
    cal = EconomicCalendar()
    events = cal.get_upcoming_events(limit=3)
    assert len(events) > 0
    assert events[0]["currency"] == "USD"
    assert events[0]["impact"] == "HIGH"
    
    status = cal.get_next_event_status()
    assert "next_event" in status
    assert "countdown_seconds" in status
    assert isinstance(status["guard_active"], bool)


@pytest.mark.asyncio
async def test_market_data_engine_tick_and_state():
    engine = MarketDataEngine()
    
    # Check history availability for all timeframes
    h1_hist = engine.get_history("H1")
    m15_hist = engine.get_history("M15")
    m5_hist = engine.get_history("M5")
    
    assert len(h1_hist) > 0
    assert len(m15_hist) > 0
    assert len(m5_hist) > 0
    assert "open" in m5_hist[0] and "close" in m5_hist[0]

    # Process tick
    engine.process_tick(2950.0, volume=5.0)
    frame = engine.get_state_frame()
    
    assert frame["xauusd"]["price"] == 2950.0
    assert "confluence_matrix" in frame
    assert "volatility" in frame
    assert "session" in frame
    assert "news" in frame
    assert frame["volatility"]["atr_m5"] > 0


@pytest.mark.asyncio
async def test_market_data_engine_listeners():
    engine = MarketDataEngine()
    received_frames = []

    def on_update(frame):
        received_frames.append(frame)

    engine.add_listener(on_update)
    engine.process_tick(2945.50)
    await engine._notify_listeners()

    assert len(received_frames) == 1
    assert received_frames[0]["xauusd"]["price"] == 2945.50

    engine.remove_listener(on_update)
    engine.process_tick(2946.00)
    await engine._notify_listeners()
    assert len(received_frames) == 1
