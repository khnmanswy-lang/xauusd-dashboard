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


def test_api_history(client):
    for tf in ["M5", "M15", "H1"]:
        response = client.get(f"/api/history/{tf}")
        assert response.status_code == 200
        candles = response.json()
        assert isinstance(candles, list)
        assert len(candles) > 0
        assert "open" in candles[0]
        assert "close" in candles[0]


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
