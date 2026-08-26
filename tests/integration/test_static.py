"""
Test static file serving and frontend assets.
"""
from starlette.testclient import TestClient
from src.server import app


def test_serve_index_html():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "XAUUSD TERMINAL" in response.text
        assert "AI SETUP SCANNER" in response.text
        assert "btn-rescan-ai" in response.text
        assert "btn-export-journal" in response.text
        assert "CSV Journal" in response.text
        assert "chart.js" in response.text
        assert "app.js" in response.text


def test_serve_css():
    with TestClient(app) as client:
        response = client.get("/static/css/dashboard.css")
        assert response.status_code == 200
        assert "--bg-app" in response.text
        assert "--gold-accent" in response.text
        assert ".ai-card" in response.text
        assert ".btn-export-csv" in response.text
        assert ".btn-rescan" in response.text


def test_serve_js():
    with TestClient(app) as client:
        res_chart = client.get("/static/js/chart.js")
        assert res_chart.status_code == 200
        assert "DashboardChart" in res_chart.text

        res_app = client.get("/static/js/app.js")
        assert res_app.status_code == 200
        assert "connectWebSocket" in res_app.text
        assert "renderAiAnalysis" in res_app.text
        assert "exportTradeJournal" in res_app.text
