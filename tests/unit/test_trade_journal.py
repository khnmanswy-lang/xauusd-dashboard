"""
Unit tests for Trade Journal Manager & CSV Exporter (src/core/trade_journal.py).
"""
import pytest
from pathlib import Path
from src.core.trade_journal import TradeJournalManager, JournalEntry


def test_trade_journal_add_and_export(tmp_path: Path):
    csv_file = tmp_path / "test_journal.csv"
    manager = TradeJournalManager(file_path=csv_file)

    assert len(manager.get_entries()) == 0

    entry1 = manager.add_entry({
        "symbol": "XAU_USD",
        "session": "LONDON",
        "killzone": "LONDON_OPEN",
        "setup_grade": "GRADE_A",
        "direction": "BULLISH_LONG",
        "confidence_pct": 90,
        "entry_price": 2932.50,
        "stop_loss": 2928.00,
        "take_profit_1": 2942.50,
        "take_profit_2": 2948.00,
        "risk_distance_usd": 4.50,
        "outcome": "TP1_HIT",
        "realized_r": 2.0,
        "confluence_factors": "Asia Low Sweep + M5 CHoCH + 65% FVG Retest"
    })

    assert entry1.id.startswith("TRD-")
    assert len(manager.get_entries()) == 1

    # Check persistence
    reloaded_manager = TradeJournalManager(file_path=csv_file)
    entries = reloaded_manager.get_entries()
    assert len(entries) == 1
    assert entries[0]["direction"] == "BULLISH_LONG"
    assert entries[0]["entry_price"] == 2932.50
    assert entries[0]["realized_r"] == 2.0

    # Check CSV export string
    csv_str = manager.export_csv_string()
    assert "timestamp_utc" in csv_str
    assert "XAU_USD" in csv_str
    assert "BULLISH_LONG" in csv_str
    assert "2932.5" in csv_str
