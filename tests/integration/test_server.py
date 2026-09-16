"""
Integration tests for FastAPI Server & WebSocket Broadcaster (src/server.py).
"""
import pytest
import json
from starlette.testclient import TestClient
from src.server import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_api_state(client):
    response = client.get("/api/state")
    assert response.status_code == 200
    data = response.json()
    assert "xauusd" in data
    assert "macro" in data
    assert "confluence_matrix" in data
    assert "volatility" in data
    assert "session" in data
    assert "news" in data
    assert "pivots" in data
    assert "multi_tf_rsi" in data
    assert "order_flow" in data
    assert "daily_range" in data
    assert "setup_analysis" in data
    assert "headline" in data["setup_analysis"]


def test_api_setup_endpoints(client):
    # Test GET /api/setup/latest
    res_get = client.get("/api/setup/latest")
    assert res_get.status_code == 200
    latest = res_get.json()
    assert "headline" in latest
    assert "setup_grade" in latest
    assert "execution_plan" in latest

    # Test POST /api/setup/scan (on-demand re-scan)
    res_post = client.post("/api/setup/scan")
    assert res_post.status_code == 200
    new_analysis = res_post.json()
    assert "headline" in new_analysis
    assert "confidence_score" in new_analysis


def test_api_matrix(client):
    response = client.get("/api/matrix")
    assert response.status_code == 200
    data = response.json()
    assert "timestamp" in data
    assert "price" in data
    assert "indicators" in data
    assert "confluence" in data
    assert "volatility" in data
    assert "overlays" in data
    assert "order_blocks" in data["overlays"]


def test_api_history(client):
    for tf in ["M1", "M5", "M15", "H1", "H4", "D1"]:
        response = client.get(f"/api/history/{tf}")
        assert response.status_code == 200
        candles = response.json()
        assert isinstance(candles, list)
        assert len(candles) > 0
        assert "open" in candles[0]
        assert "close" in candles[0]
        assert "ema50" in candles[0]
        assert "vwma20" in candles[0]


def test_api_news(client):
    response = client.get("/api/news?limit=3")
    assert response.status_code == 200
    news = response.json()
    assert isinstance(news, list)
    assert len(news) <= 3
    assert news[0]["currency"] == "USD"


def test_api_risk_calculate(client):
    payload = {
        "account_balance": 10000.0,
        "risk_percentage": 1.0,
        "atr_m5": 2.0,
        "sl_multiplier": 1.5,
        "current_price": 2935.0
    }
    response = client.post("/api/risk/calculate", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["account_balance"] == 10000.0
    assert result["calculated_lots"] == 0.33
    assert result["sl_distance_usd"] == 3.0
    assert result["tp_1r_price"] == 2938.0


def test_websocket_stream(client):
    with client.websocket_connect("/ws/stream") as websocket:
        # Should receive initial state JSON immediately
        data_text = websocket.receive_text()
        data = json.loads(data_text)
        assert "xauusd" in data
        assert "confluence_matrix" in data

        # Send ping
        websocket.send_text("ping")
        pong_text = websocket.receive_text()
        pong = json.loads(pong_text)
        assert pong.get("type") == "pong" or "xauusd" in pong


def test_api_journal_endpoints(client):
    # 1. Test POST /api/journal/record
    entry_payload = {
        "symbol": "XAU_USD",
        "session": "LONDON",
        "killzone": "LONDON_OPEN",
        "setup_grade": "GRADE_A",
        "direction": "BULLISH_LONG",
        "confidence_pct": 95,
        "entry_price": 2932.40,
        "stop_loss": 2928.00,
        "take_profit_1": 2941.20,
        "take_profit_2": 2945.00,
        "risk_distance_usd": 4.40,
        "outcome": "TP1_HIT",
        "realized_r": 2.0,
        "confluence_factors": "M5 CHoCH + FVG 65% Retest + VWAP Alignment",
        "ai_thesis": "Clean expansion out of London liquidity sweep."
    }
    res_rec = client.post("/api/journal/record", json=entry_payload)
    assert res_rec.status_code == 200
    rec_data = res_rec.json()
    assert rec_data["status"] == "success"
    assert rec_data["entry"]["direction"] == "BULLISH_LONG"

    # 2. Test GET /api/journal/list
    res_list = client.get("/api/journal/list?limit=10")
    assert res_list.status_code == 200
    entries = res_list.json()
    assert isinstance(entries, list)
    assert len(entries) >= 1
    assert entries[0]["symbol"] == "XAU_USD"

    # 3. Test GET /api/journal/export
    res_export = client.get("/api/journal/export")
    assert res_export.status_code == 200
    assert res_export.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=xauusd_trade_journal_" in res_export.headers.get("content-disposition", "")
    csv_text = res_export.text
    assert "timestamp_utc" in csv_text
    assert "BULLISH_LONG" in csv_text
    assert "2932.4" in csv_text
