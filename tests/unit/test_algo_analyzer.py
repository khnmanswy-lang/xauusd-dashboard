"""
Unit tests for Pure Deterministic Algorithmic Setup Analyzer (src/core/algo_analyzer.py).
"""
import pytest
import asyncio
from unittest.mock import MagicMock
from datetime import datetime, timezone

from src.core.algo_analyzer import AlgoSetupAnalyzer
from src.integrations.market_data import MarketDataEngine


def test_algo_analyzer_deterministic_grade_a():
    mock_market = MagicMock(spec=MarketDataEngine)
    analyzer = AlgoSetupAnalyzer(market_engine=mock_market)

    mock_frame = {
        "xauusd": {"price": 2933.0, "spread": 0.20},
        "session": {
            "active_session": "LONDON",
            "killzone": "LONDON_OPEN",
            "asia_high": 2945.0,
            "asia_low": 2928.0,
            "recent_sweep": "ASIA_LOW_SWEPT"
        },
        "volatility": {"adr_used_pct": 45.0},
        "news": {"guard_active": False},
        "setup_scan": {
            "grade": "GRADE_A",
            "direction": "BULLISH_LONG",
            "confidence_score": 0.92,
            "suggested_entry": 2932.50,
            "suggested_sl": 2927.50,
            "suggested_tp1": 2942.50,
            "suggested_tp2": 2945.00,
            "risk_reward_ratio": 2.0,
            "invalidation_trigger": "M5 close below $2927.50"
        }
    }

    result = analyzer._generate_analysis(mock_frame)
    assert result["setup_grade"] == "GRADE_A"
    assert result["direction"] == "BULLISH_LONG"
    assert result["confidence_score"] == 0.92
    assert "ASIA_LOW_SWEPT" in result["headline"] or "Asian Low" in result["headline"]
    assert len(result["order_flow_breakdown"]) >= 2
    assert result["execution_plan"]["entry"] == 2932.50
    assert result["execution_plan"]["stop_loss"] == 2927.50
    assert result["execution_plan"]["take_profit_1"] == 2942.50
    assert "psychology_warning" in result


def test_algo_analyzer_trailing_stop_adjustment():
    mock_market = MagicMock(spec=MarketDataEngine)
    analyzer = AlgoSetupAnalyzer(market_engine=mock_market)

    previous_setup = {
        "setup_grade": "GRADE_A",
        "direction": "BULLISH_LONG",
        "execution_plan": {
            "entry": 2930.00,
            "stop_loss": 2925.00,
            "take_profit_1": 2940.00,
            "take_profit_2": 2948.00
        }
    }

    # Price has expanded to 2934.50 (+$4.50 in profit)
    mock_frame = {
        "xauusd": {"price": 2934.50},
        "session": {"active_session": "LONDON", "killzone": "OPEN"},
        "volatility": {"adr_used_pct": 50.0},
        "news": {"guard_active": False},
        "setup_scan": {"grade": "GRADE_A", "direction": "BULLISH_LONG", "confidence_score": 0.95}
    }

    adjusted = analyzer._generate_analysis(mock_frame, previous_analysis=previous_setup)
    assert "Break-Even" in adjusted["headline"]
    assert adjusted["execution_plan"]["stop_loss"] == 2930.50  # Trailed SL


@pytest.mark.asyncio
async def test_algo_analyzer_evaluate_market_flow():
    mock_engine = MagicMock(spec=MarketDataEngine)
    mock_engine.get_state_frame.return_value = {
        "xauusd": {"price": 2935.0, "spread": 0.20},
        "session": {"active_session": "LONDON", "killzone": "OPEN", "recent_sweep": None},
        "volatility": {"adr_used_pct": 30.0},
        "news": {"guard_active": False},
        "setup_scan": {"grade": "NO_SETUP", "direction": "NEUTRAL", "confidence_score": 0.20}
    }

    analyzer = AlgoSetupAnalyzer(market_engine=mock_engine)

    received_payloads = []
    def listener(payload):
        received_payloads.append(payload)

    analyzer.add_listener(listener)

    result = await analyzer.evaluate_market()
    assert result["setup_grade"] == "NO_SETUP"
    assert result["direction"] == "NEUTRAL"
    assert len(received_payloads) == 1
    assert received_payloads[0]["type"] == "SETUP_SCAN_UPDATE"


@pytest.mark.asyncio
async def test_algo_analyzer_plan_handover_and_rejection_lifecycle():
    mock_market = MagicMock(spec=MarketDataEngine)
    analyzer = AlgoSetupAnalyzer(market_engine=mock_market)

    # 1. New displacement setup far from deep FVG (suggested entry 2930.0, current price 2934.0)
    frame_far = {
        "xauusd": {"price": 2934.0},
        "session": {"active_session": "LONDON", "killzone": "OPEN", "recent_sweep": "ASIA_LOW_SWEPT"},
        "volatility": {"adr_used_pct": 40.0},
        "news": {"guard_active": False},
        "setup_scan": {
            "grade": "GRADE_A",
            "direction": "BULLISH_LONG",
            "confidence_score": 0.90,
            "suggested_entry": 2930.0,
            "suggested_sl": 2926.0,
            "suggested_tp1": 2940.0
        }
    }

    plan_1 = analyzer._generate_analysis(frame_far)
    assert plan_1["plan_status"] == "WAITING_FOR_TRIGGER"
    assert "PLAN HANDOVER" in plan_1["headline"]
    assert plan_1["trigger_condition"]["target_level"] == 2930.0

    # 2. Next evaluation: price is at 2932.0 (still waiting, silent handover)
    frame_handover = {
        "xauusd": {"price": 2932.0},
        "session": {"active_session": "LONDON", "killzone": "OPEN"},
        "volatility": {"adr_used_pct": 45.0},
        "news": {"guard_active": False},
        "setup_scan": {"grade": "GRADE_A", "direction": "BULLISH_LONG", "confidence_score": 0.90}
    }
    plan_2 = analyzer._generate_analysis(frame_handover, previous_analysis=plan_1)
    assert plan_2["plan_status"] == "WAITING_FOR_TRIGGER"
    assert "Dist: $2.00" in plan_2["handover_notes"]

    # 3. Next evaluation: price pulls back directly into trigger zone ($2930.0) -> TRIGGER FIRED!
    frame_triggered = {
        "xauusd": {"price": 2930.20},
        "session": {"active_session": "LONDON", "killzone": "OPEN"},
        "volatility": {"adr_used_pct": 50.0},
        "news": {"guard_active": False},
        "setup_scan": {"grade": "GRADE_A", "direction": "BULLISH_LONG", "confidence_score": 0.90}
    }
    plan_3 = analyzer._generate_analysis(frame_triggered, previous_analysis=plan_2)
    assert plan_3["plan_status"] == "READY_TO_EXECUTE"
    assert "TRIGGER FIRED" in plan_3["headline"]

    # 4. Next evaluation: price falls below invalidation level ($2925.0 < $2926.0) -> PLAN REJECTED!
    frame_invalidated = {
        "xauusd": {"price": 2925.00},
        "session": {"active_session": "LONDON", "killzone": "OPEN"},
        "volatility": {"adr_used_pct": 55.0},
        "news": {"guard_active": False},
        "setup_scan": {"grade": "NO_SETUP", "direction": "NEUTRAL", "confidence_score": 0.20}
    }
    plan_4 = analyzer._generate_analysis(frame_invalidated, previous_analysis=plan_1)
    assert plan_4["plan_status"] == "PLAN_REJECTED"
    assert "PLAN REJECTED" in plan_4["headline"]
    assert "breached invalidation level" in plan_4["rejection_reason"]


def test_algo_analyzer_guards_prevent_execution():
    mock_market = MagicMock(spec=MarketDataEngine)
    analyzer = AlgoSetupAnalyzer(market_engine=mock_market)

    # Frame with ADR Exhaustion (>80%)
    frame_adr_exhausted = {
        "xauusd": {"price": 2950.0},
        "session": {"active_session": "NY", "killzone": "OPEN"},
        "volatility": {"adr_used_pct": 88.0},
        "news": {"guard_active": False},
        "setup_scan": {
            "grade": "GRADE_A",
            "direction": "BULLISH_LONG",
            "confidence_score": 0.90,
            "suggested_entry": 2949.0,
            "suggested_sl": 2945.0,
            "suggested_tp1": 2960.0
        }
    }

    result = analyzer._generate_analysis(frame_adr_exhausted)
    assert result["plan_status"] == "PLAN_REJECTED"
    assert "ADR Exhausted" in result["headline"]
    assert "ADR capacity exhausted" in result["rejection_reason"]
    assert result["execution_plan"]["entry"] is None
