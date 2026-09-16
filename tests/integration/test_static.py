"""
Test static file serving and frontend assets for Clean 4-Timeframe Dashboard Terminal.
"""
from starlette.testclient import TestClient
from src.server import app


def test_serve_index_html():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "XAUUSD" in response.text
        assert "SYMBOL:" in response.text
        assert "XAU/USD" in response.text
        assert "SPREAD:" in response.text
        assert "SESSION STATUS" in response.text
        assert "ADR (20D):" in response.text
        assert "DAILY RANGE (H-L)" in response.text
        assert "DXY INDEX:" in response.text
        assert "quad-chart-grid" in response.text
        assert "chart-m1" in response.text
        assert "chart-m15" in response.text
        assert "chart-h1" in response.text
        assert "chart-h4" in response.text
        assert "[MULTI-TF RSI]" in response.text
        assert "[PIVOT POINTS]" in response.text
        assert "[ORDER FLOW]" in response.text
        assert "CSV Journal" in response.text
        assert "chart.js" in response.text
        assert "app.js" in response.text


def test_serve_css():
    with TestClient(app) as client:
        response = client.get("/static/css/dashboard.css")
        assert response.status_code == 200
        assert "--bg-canvas" in response.text
        assert "--gold-accent" in response.text
        assert ".top-macro-bar" in response.text
        assert ".quad-chart-grid" in response.text
        assert ".right-technical-sidebar" in response.text


def test_serve_js():
    with TestClient(app) as client:
        res_chart = client.get("/static/js/chart.js")
        assert res_chart.status_code == 200
        assert "MultiTimeframeChartGrid" in res_chart.text
        assert "SingleTimeframeChart" in res_chart.text

        res_app = client.get("/static/js/app.js")
        assert res_app.status_code == 200
        assert "connectWebSocket" in res_app.text
        assert "renderState" in res_app.text
