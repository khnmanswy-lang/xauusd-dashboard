"""
Unit tests for OANDA v20 REST & Streaming Integration (src/integrations/oanda_client.py).
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from src.config.settings import OandaSettings, AiSettings
from src.integrations.oanda_client import OandaClient, parse_rfc3339_to_unix
from src.core.indicators import Candle
from src.integrations.market_data import MarketDataEngine


def test_oanda_settings_and_urls():
    practice_cfg = OandaSettings(api_key="test_key", account_id="101-004-12345-001", environment="practice")
    assert practice_cfg.is_configured() is True
    assert practice_cfg.rest_base_url == "https://api-fxpractice.oanda.com/v3"
    assert practice_cfg.stream_base_url == "https://stream-fxpractice.oanda.com/v3"

    live_cfg = OandaSettings(api_key="live_key", account_id="001-001-12345-001", environment="live")
    assert live_cfg.is_configured() is True
    assert live_cfg.rest_base_url == "https://api-fxtrade.oanda.com/v3"
    assert live_cfg.stream_base_url == "https://stream-fxtrade.oanda.com/v3"

    placeholder_cfg = OandaSettings(api_key="your_oanda_api_key", account_id="101-004-xxxxxxx-001")
    assert placeholder_cfg.is_configured() is False

    empty_cfg = OandaSettings(api_key="", account_id="")
    assert empty_cfg.is_configured() is False


def test_ai_settings_configured():
    gemini_cfg = AiSettings(provider="gemini", gemini_api_key="AIzaSyDummyKey123")
    assert gemini_cfg.is_configured() is True

    openai_cfg = AiSettings(provider="openai", openai_api_key="sk-proj-dummy")
    assert openai_cfg.is_configured() is True

    ollama_cfg = AiSettings(provider="ollama", ollama_base_url="http://localhost:11434")
    assert ollama_cfg.is_configured() is True

    placeholder_ai = AiSettings(provider="gemini", gemini_api_key="your_gemini_api_key_here")
    assert placeholder_ai.is_configured() is False


def test_parse_rfc3339_to_unix():
    ts_str = "2026-08-24T14:30:00.000000000Z"
    unix_ts = parse_rfc3339_to_unix(ts_str)
    assert isinstance(unix_ts, int)
    dt = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
    assert dt.year == 2026
    assert dt.month == 8
    assert dt.day == 24
    assert dt.hour == 14
    assert dt.minute == 30

    # Test corrupted format fallback
    fallback_ts = parse_rfc3339_to_unix("invalid-date-string")
    assert isinstance(fallback_ts, int)
    assert fallback_ts > 0


@pytest.mark.asyncio
async def test_oanda_client_unconfigured():
    cfg = OandaSettings(api_key="", account_id="")
    client = OandaClient(cfg)
    assert client.is_configured() is False

    pricing = await client.fetch_pricing()
    assert pricing is None

    candles = await client.fetch_candles()
    assert candles == []


@pytest.mark.asyncio
async def test_oanda_client_fetch_pricing_mocked():
    cfg = OandaSettings(api_key="valid_token", account_id="101-004-999-001", environment="practice")
    client = OandaClient(cfg)

    mock_resp_data = {
        "prices": [
            {
                "instrument": "XAU_USD",
                "time": "2026-08-24T14:30:00.000000000Z",
                "bids": [{"price": "2935.20", "liquidity": 100000}],
                "asks": [{"price": "2935.40", "liquidity": 100000}],
                "closeoutBid": "2935.20",
                "closeoutAsk": "2935.40"
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_resp_data

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await client.fetch_pricing("XAU_USD")

        assert result is not None
        assert result["symbol"] == "XAU_USD"
        assert result["bid"] == 2935.20
        assert result["ask"] == 2935.40
        assert result["price"] == 2935.30
        assert result["spread"] == 0.20
        assert result["timestamp"] > 0


@pytest.mark.asyncio
async def test_oanda_client_fetch_candles_mocked():
    cfg = OandaSettings(api_key="valid_token", account_id="101-004-999-001", environment="practice")
    client = OandaClient(cfg)

    mock_candle_data = {
        "candles": [
            {
                "complete": True,
                "volume": 240,
                "time": "2026-08-24T14:00:00.000000000Z",
                "mid": {
                    "o": "2930.00",
                    "h": "2935.50",
                    "l": "2928.50",
                    "c": "2934.00"
                }
            },
            {
                "complete": True,
                "volume": 310,
                "time": "2026-08-24T14:01:00.000000000Z",
                "mid": {
                    "o": "2934.00",
                    "h": "2938.00",
                    "l": "2933.00",
                    "c": "2937.50"
                }
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_candle_data

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        candles = await client.fetch_candles("XAU_USD", "M1", 2)

        assert len(candles) == 2
        assert isinstance(candles[0], Candle)
        assert candles[0].open == 2930.00
        assert candles[0].high == 2935.50
        assert candles[0].low == 2928.50
        assert candles[0].close == 2934.00
        assert candles[0].volume == 240.0


@pytest.mark.asyncio
async def test_market_data_engine_oanda_integration():
    mock_oanda = MagicMock(spec=OandaClient)
    mock_oanda.is_configured.return_value = True
    mock_oanda.fetch_candles = AsyncMock(return_value=[
        Candle(timestamp=1740000000 + i * 60, open=2930.0 + i * 0.1, high=2931.0 + i * 0.1, low=2929.0 + i * 0.1, close=2930.5 + i * 0.1, volume=50.0)
        for i in range(50)
    ])
    mock_oanda.start_pricing_stream = AsyncMock()
    mock_oanda.stop = AsyncMock()

    engine = MarketDataEngine(oanda_client=mock_oanda)
    await engine.start()

    assert mock_oanda.fetch_candles.called
    assert mock_oanda.start_pricing_stream.called

    # Test tick callback
    engine._on_oanda_price_tick(price=2942.50, bid=2942.40, ask=2942.60, timestamp=1740003000)
    frame = engine.get_state_frame()
    assert frame["xauusd"]["price"] == 2942.50
    assert frame["xauusd"]["spread"] == 0.20

    await engine.stop()
    assert mock_oanda.stop.called
