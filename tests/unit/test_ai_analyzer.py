"""
Unit tests for AI Setup Analyzer & AI Client (src/integrations/ai_client.py, src/core/ai_analyzer.py).
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from src.config.settings import AiSettings
from src.integrations.ai_client import AiClient
from src.core.ai_analyzer import AiSetupAnalyzer
from src.integrations.market_data import MarketDataEngine
from src.core.setup_scanner import SetupResult


def test_ai_client_deterministic_grade_a():
    client = AiClient(AiSettings(provider="gemini", gemini_api_key=""))
    assert client.is_configured() is False

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

    result = client._generate_deterministic_analysis(mock_frame)
    assert result["setup_grade"] == "GRADE_A"
    assert result["direction"] == "BULLISH_LONG"
    assert result["confidence_score"] == 0.92
    assert "Asian Low" in result["headline"]
    assert len(result["order_flow_breakdown"]) >= 2
    assert result["execution_plan"]["entry"] == 2932.50
    assert result["execution_plan"]["stop_loss"] == 2927.50
    assert result["execution_plan"]["take_profit_1"] == 2942.50
    assert "psychology_warning" in result


def test_ai_client_trailing_stop_adjustment():
    client = AiClient()
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

    adjusted = client._generate_deterministic_analysis(mock_frame, previous_analysis=previous_setup)
    assert "Break-Even" in adjusted["headline"]
    assert adjusted["execution_plan"]["stop_loss"] == 2930.50  # Trailed SL


@pytest.mark.asyncio
async def test_ai_client_gemini_mocked():
    cfg = AiSettings(provider="gemini", gemini_api_key="AIzaDummyKey")
    client = AiClient(cfg)
    assert client.is_configured() is True

    mock_llm_json = {
        "headline": "GRADE A BULLISH LONG: Asia Sweep Confirmed",
        "setup_grade": "GRADE_A",
        "direction": "BULLISH_LONG",
        "confidence_score": 0.90,
        "thesis": "High probability long following liquidity sweep.",
        "order_flow_breakdown": ["Asia Low swept", "M5 CHoCH printed"],
        "execution_plan": {
            "entry": 2932.0, "stop_loss": 2928.0, "take_profit_1": 2940.0, "take_profit_2": 2945.0,
            "risk_reward_ratio": 2.0, "invalidation": "Close below $2928"
        },
        "psychology_warning": "Strict 1% risk discipline."
    }

    mock_gemini_resp = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps(mock_llm_json)}]
                }
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_gemini_resp

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        analysis = await client.generate_setup_analysis({"xauusd": {"price": 2932.0}})
        assert analysis["setup_grade"] == "GRADE_A"
        assert analysis["confidence_score"] == 0.90
        assert analysis["execution_plan"]["entry"] == 2932.0


@pytest.mark.asyncio
async def test_ai_client_openai_mocked():
    cfg = AiSettings(provider="openai", openai_api_key="sk-proj-dummy")
    client = AiClient(cfg)
    assert client.is_configured() is True

    mock_llm_json = {
        "headline": "GRADE A SHORT: Asia High Swept",
        "setup_grade": "GRADE_A",
        "direction": "BEARISH_SHORT",
        "confidence_score": 0.88,
        "thesis": "Bearish reversal confirmed.",
        "order_flow_breakdown": ["Asia High swept", "M5 CHoCH down"],
        "execution_plan": {
            "entry": 2945.0, "stop_loss": 2949.0, "take_profit_1": 2937.0, "take_profit_2": 2930.0,
            "risk_reward_ratio": 2.0, "invalidation": "Close above $2949"
        },
        "psychology_warning": "No FOMO entries."
    }

    mock_openai_resp = {
        "choices": [
            {
                "message": {"content": json.dumps(mock_llm_json)}
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_openai_resp

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        analysis = await client.generate_setup_analysis({"xauusd": {"price": 2945.0}})
        assert analysis["setup_grade"] == "GRADE_A"
        assert analysis["direction"] == "BEARISH_SHORT"


@pytest.mark.asyncio
async def test_ai_analyzer_evaluate_market_flow():
    engine = MarketDataEngine()
    analyzer = AiSetupAnalyzer(market_engine=engine)

    received_updates = []

    def on_update(payload):
        received_updates.append(payload)

    analyzer.add_listener(on_update)

    result = await analyzer.evaluate_market()
    assert "headline" in result
    assert "setup_grade" in result
    assert "execution_plan" in result
    assert len(received_updates) == 1
    assert received_updates[0]["type"] == "AI_ANALYSIS_UPDATE"

    cached = analyzer.get_latest_analysis()
    assert cached["headline"] == result["headline"]


def test_ai_client_plan_handover_and_rejection_lifecycle():
    client = AiClient()
    pending_plan = {
        "setup_grade": "GRADE_A",
        "direction": "BULLISH_LONG",
        "confidence_score": 0.85,
        "plan_status": "WAITING_FOR_TRIGGER",
        "trigger_condition": {
            "condition_type": "FVG_RETEST",
            "target_level": 2932.00,
            "invalidation_level": 2927.00,
            "description": "Wait for pullback to 2932.00"
        },
        "execution_plan": {
            "entry": 2932.00,
            "stop_loss": 2927.00,
            "take_profit_1": 2942.00,
            "take_profit_2": 2948.00
        }
    }

    # Case 1: Still waiting (price at 2936.00) -> Silent Handover
    frame_waiting = {
        "xauusd": {"price": 2936.00},
        "volatility": {"adr_used_pct": 50.0},
        "news": {"guard_active": False}
    }
    res_waiting = client._generate_deterministic_analysis(frame_waiting, previous_analysis=pending_plan)
    assert res_waiting["plan_status"] == "WAITING_FOR_TRIGGER"
    assert "Handover" in res_waiting["headline"] or res_waiting["handover_notes"] is not None

    # Case 2: Target touched (price at 2932.20) -> Trigger Fired!
    frame_triggered = {
        "xauusd": {"price": 2932.20},
        "volatility": {"adr_used_pct": 50.0},
        "news": {"guard_active": False}
    }
    res_triggered = client._generate_deterministic_analysis(frame_triggered, previous_analysis=pending_plan)
    assert res_triggered["plan_status"] == "READY_TO_EXECUTE"
    assert res_triggered["confidence_score"] >= 0.85

    # Case 3: Invalidation breached (price drops to 2925.00 < 2927.00) -> Plan Rejected!
    frame_rejected = {
        "xauusd": {"price": 2925.00},
        "volatility": {"adr_used_pct": 50.0},
        "news": {"guard_active": False}
    }
    res_rejected = client._generate_deterministic_analysis(frame_rejected, previous_analysis=pending_plan)
    assert res_rejected["plan_status"] == "PLAN_REJECTED"
    assert res_rejected["setup_grade"] == "NO_SETUP"
    assert res_rejected["rejection_reason"] is not None
    assert "invalidated" in res_rejected["rejection_reason"].lower()


def test_ai_client_guards_prevent_execution_confirmed():
    cfg = AiSettings()
    client = AiClient(cfg)

    # Frame with GRADE_B setup but ADR capacity exhausted at 88%
    frame_adr_blocked = {
        "xauusd": {"price": 2935.0},
        "volatility": {"adr_used_pct": 88.0, "atr_m5": 2.0},
        "news": {"guard_active": False},
        "setup_scan": {
            "grade": "GRADE_B",
            "direction": "BEARISH_SHORT",
            "confidence_score": 0.65,
            "suggested_entry": 2935.0,
            "suggested_sl": 2939.0
        },
        "session": {"active_session": "ASIA", "killzone": "OPEN"}
    }

    res = client._generate_deterministic_analysis(frame_adr_blocked)
    # Must NOT say Execution Confirmed!
    assert "Execution Confirmed" not in res["headline"]
    assert "STANDING ASIDE" in res["headline"]
    assert res["plan_status"] == "PLAN_REJECTED"
    assert "ADR Exhausted" in res["headline"]
