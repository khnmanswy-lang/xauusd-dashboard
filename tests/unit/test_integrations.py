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
    
    # Check history availability for all institutional timeframes
    m1_hist = engine.get_history("M1")
    m5_hist = engine.get_history("M5")
    m15_hist = engine.get_history("M15")
    h1_hist = engine.get_history("H1")
    h4_hist = engine.get_history("H4")
    d1_hist = engine.get_history("D1")
    
    assert len(m1_hist) > 0
    assert len(m5_hist) > 0
    assert len(m15_hist) > 0
    assert len(h1_hist) > 0
    assert len(h4_hist) > 0
    assert len(d1_hist) > 0
    
    # Check enriched overlay indicator fields in history
    first_m5 = m5_hist[-1]
    assert "open" in first_m5 and "close" in first_m5
    assert "ema9" in first_m5 and "ema20" in first_m5
    assert "ema50" in first_m5 and "ema200" in first_m5
    assert "vwma20" in first_m5 and "bb_upper" in first_m5

    # Process tick
    engine.process_tick(2950.0, volume=5.0)
    frame = engine.get_state_frame()
    
    assert frame["xauusd"]["price"] == 2950.0
    assert "confluence_matrix" in frame
    assert "indicators_matrix" in frame
    assert "volatility" in frame
    assert "session" in frame
    assert "news" in frame
    assert "overlays" in frame
    assert "order_blocks" in frame["overlays"]
    assert "volume_flow" in frame["indicators_matrix"]
    assert "macd" in frame["indicators_matrix"]
    assert "stochastic_rsi" in frame["indicators_matrix"]
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


@pytest.mark.asyncio
async def test_market_data_engine_fetch_real_daily_history():
    engine = MarketDataEngine()
    engine._seed_daily_history(current_price=2950.0)
    assert len(engine._daily_df) >= 20
    assert "high" in engine._daily_df.columns and "low" in engine._daily_df.columns
    
    # Verify ADR calculation with daily history
    engine._recompute_all()
    frame = engine.get_state_frame()
    assert frame["volatility"]["adr_total"] > 10.0

