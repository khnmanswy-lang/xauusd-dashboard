"""
Unit tests for Auto-Execution Sentry & OANDA Practice Trader (src/core/auto_trader.py).
"""
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.core.auto_trader import AutoTrader
from src.core.trade_journal import TradeJournalManager


@pytest.fixture
def mock_dependencies(tmp_path: Path):
    market_engine = MagicMock()
    market_engine.get_state_frame.return_value = {
        "xauusd": {"price": 2935.0},
        "volatility": {"adr_used_pct": 45.0, "atr_m5": 2.0},
        "session": {"active_session": "LONDON", "killzone": "LONDON_OPEN"},
        "news": {"guard_active": False}
    }

    ai_analyzer = MagicMock()
    ai_analyzer.get_latest_analysis.return_value = {
        "plan_status": "READY_TO_EXECUTE",
        "setup_grade": "GRADE_A",
        "direction": "BULLISH_LONG",
        "confidence_score": 0.90,
        "execution_plan": {
            "entry": 2932.40,
            "stop_loss": 2928.00,
            "take_profit_1": 2941.20,
            "take_profit_2": 2945.00
        },
        "order_flow_breakdown": ["London low sweep", "M5 CHoCH", "65% FVG retest"],
        "thesis": "High conviction London expansion"
    }

    oanda_client = AsyncMock()
    oanda_client.is_configured = MagicMock(return_value=True)
    oanda_client.get_account_summary.return_value = {"balance": "10000.00"}
    oanda_client.get_open_trades.return_value = []
    oanda_client.create_order.return_value = {
        "orderFillTransaction": {"id": "101", "price": "2932.40"}
    }
    oanda_client.update_trade_stop_loss.return_value = True

    journal_csv = tmp_path / "test_trader_journal.csv"
    trade_journal = TradeJournalManager(file_path=journal_csv)

    return market_engine, ai_analyzer, oanda_client, trade_journal


def test_autotrader_toggle_and_killzone(mock_dependencies):
    market_engine, ai_analyzer, oanda_client, trade_journal = mock_dependencies
    trader = AutoTrader(market_engine, ai_analyzer, oanda_client, trade_journal, enabled=True)

    assert trader.enabled is True
    trader.toggle()
    assert trader.enabled is False
    trader.toggle(True)
    assert trader.enabled is True

    # Active Session: 01:30 UTC -> True
    dt_asia = datetime(2026, 8, 26, 1, 30, tzinfo=timezone.utc)
    assert trader.is_in_killzone(dt_asia) is True

    # Market Closed / Off-hours: 23:00 UTC -> False
    dt_closed = datetime(2026, 8, 26, 23, 0, tzinfo=timezone.utc)
    assert trader.is_in_killzone(dt_closed) is False


@pytest.mark.asyncio
async def test_autotrader_idempotent_open_position(mock_dependencies):
    market_engine, ai_analyzer, oanda_client, trade_journal = mock_dependencies
    trader = AutoTrader(market_engine, ai_analyzer, oanda_client, trade_journal, enabled=True)

    # Simulate existing open trade in profit (+$4.00), should trigger Trailing Stop
    oanda_client.get_open_trades.return_value = [{
        "id": "TRD-99",
        "price": "2930.00",
        "currentUnits": "10",
        "stopLossOrder": {"price": "2926.00"}
    }]
    # Current price is 2935.0 (profit = $5.00)
    res = await trader.evaluate_and_trade()
    assert res["status"] == "TRAILING_UPDATED"
    assert res["trade_id"] == "TRD-99"
    assert res["new_stop_loss"] == 2930.50
    oanda_client.update_trade_stop_loss.assert_called_once_with("TRD-99", 2930.50)
    # Order placement should NOT have been called
    oanda_client.create_order.assert_not_called()


@pytest.mark.asyncio
async def test_autotrader_execute_trade_flow(mock_dependencies):
    market_engine, ai_analyzer, oanda_client, trade_journal = mock_dependencies
    trader = AutoTrader(market_engine, ai_analyzer, oanda_client, trade_journal, enabled=True)

    # Force is_in_killzone to True for deterministic test
    trader.is_in_killzone = MagicMock(return_value=True)

    res = await trader.evaluate_and_trade()
    assert res["status"] == "EXECUTED"
    assert res["direction"] == "BULLISH_LONG"
    assert res["entry_price"] == 2932.40
    assert res["stop_loss"] == 2928.00
    assert res["units"] > 0

    # Verify OANDA order dispatch
    oanda_client.create_order.assert_called_once()

    # Verify Trade Journal entry
    entries = trade_journal.get_entries()
    assert len(entries) == 1
    assert entries[0]["direction"] == "BULLISH_LONG"
    assert entries[0]["entry_price"] == 2932.40
