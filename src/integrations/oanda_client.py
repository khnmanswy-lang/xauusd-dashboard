"""
OANDA v20 REST & Streaming API Client for XAUUSD Multi-Timeframe Terminal.
Handles institutional live spot quote streaming, historical candle fetching,
and automatic reconnect with exponential backoff on transient network drops.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any
import httpx

from src.config.settings import OandaSettings, settings
from src.core.indicators import Candle

logger = logging.getLogger(__name__)


def parse_rfc3339_to_unix(rfc3339_str: str) -> int:
    """
    Parse OANDA RFC3339 timestamp (e.g. '2026-08-24T14:30:00.000000000Z')
    into standard Unix timestamp in seconds.
    """
    try:
        # Strip trailing Z and nanoseconds if longer than microseconds (6 digits)
        clean_str = rfc3339_str.replace("Z", "+00:00")
        if "." in clean_str:
            base, frac = clean_str.split(".", 1)
            # Retain up to 6 microsecond digits + timezone offset
            tz_idx = frac.find("+") if "+" in frac else (frac.find("-") if "-" in frac else len(frac))
            frac_digits = frac[:min(6, tz_idx)]
            tz_part = frac[tz_idx:] if tz_idx < len(frac) else "+00:00"
            clean_str = f"{base}.{frac_digits}{tz_part}"
        dt = datetime.fromisoformat(clean_str)
        return int(dt.timestamp())
    except Exception as e:
        logger.debug("Failed parsing OANDA timestamp %s: %s", rfc3339_str, e)
        return int(datetime.now(timezone.utc).timestamp())


class OandaClient:
    """
    Async client for OANDA v20 Practice & Live API.
    Provides live quote streaming and historical candlestick ingestion.
    """

    def __init__(self, oanda_settings: Optional[OandaSettings] = None):
        self.settings = oanda_settings or settings.oanda
        self._running: bool = False
        self._stream_task: Optional[asyncio.Task] = None

    def is_configured(self) -> bool:
        """Returns True if OANDA credentials are present and not placeholders."""
        return self.settings.is_configured()

    def _get_headers(self) -> Dict[str, str]:
        """Generate authorized headers for OANDA API."""
        return {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
            "Accept-Datetime-Format": "RFC3339",
            "User-Agent": "XAUUSD-Terminal-v1"
        }

    async def fetch_pricing(self, instrument: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Fetch real-time snapshot quote for instrument from OANDA REST API.
        Endpoint: GET /v3/accounts/{accountID}/pricing?instruments=XAU_USD
        """
        if not self.is_configured():
            return None

        sym = instrument or self.settings.symbol
        url = f"{self.settings.rest_base_url}/accounts/{self.settings.account_id}/pricing"
        params = {"instruments": sym}

        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.get(url, headers=self._get_headers(), params=params)
                if res.status_code == 200:
                    data = res.json()
                    prices = data.get("prices", [])
                    if prices:
                        p0 = prices[0]
                        bids = p0.get("bids", [])
                        asks = p0.get("asks", [])
                        bid = float(bids[0]["price"]) if bids else float(p0.get("closeoutBid", 0.0))
                        ask = float(asks[0]["price"]) if asks else float(p0.get("closeoutAsk", 0.0))
                        mid = round((bid + ask) / 2.0, 2)
                        spread = round(ask - bid, 2)
                        ts = parse_rfc3339_to_unix(p0.get("time", ""))
                        return {
                            "symbol": sym,
                            "price": mid,
                            "bid": bid,
                            "ask": ask,
                            "spread": spread,
                            "timestamp": ts
                        }
                else:
                    logger.warning("OANDA pricing fetch returned HTTP %d", res.status_code)
        except Exception as e:
            logger.debug("Error fetching OANDA pricing: %s", e)
        return None

    async def fetch_candles(
        self,
        instrument: Optional[str] = None,
        granularity: str = "M1",
        count: int = 500
    ) -> List[Candle]:
        """
        Fetch historical candlestick data from OANDA REST API.
        Endpoint: GET /v3/instruments/{instrument}/candles?granularity=M1&count=500&price=M
        """
        if not self.is_configured():
            return []

        sym = instrument or self.settings.symbol
        url = f"{self.settings.rest_base_url}/instruments/{sym}/candles"
        params = {
            "granularity": granularity.upper(),
            "count": min(count, 5000),
            "price": "M"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=self._get_headers(), params=params)
                if res.status_code == 200:
                    data = res.json()
                    raw_candles = data.get("candles", [])
                    result: List[Candle] = []
                    for c in raw_candles:
                        mid = c.get("mid", {})
                        if not mid:
                            continue
                        ts = parse_rfc3339_to_unix(c.get("time", ""))
                        result.append(Candle(
                            timestamp=ts,
                            open=float(mid.get("o", 0.0)),
                            high=float(mid.get("h", 0.0)),
                            low=float(mid.get("l", 0.0)),
                            close=float(mid.get("c", 0.0)),
                            volume=float(c.get("volume", 0.0))
                        ))
                    logger.info("Successfully fetched %d %s candles from OANDA v20 (%s)", len(result), granularity, sym)
                    return result
                else:
                    logger.warning("OANDA candles fetch returned HTTP %d: %s", res.status_code, res.text[:200])
        except Exception as e:
            logger.debug("Error fetching OANDA candles: %s", e)
        return []

    async def start_pricing_stream(
        self,
        callback: Callable[[float, float, float, int], Any],
        instrument: Optional[str] = None
    ):
        """
        Start continuous OANDA pricing stream.
        Endpoint: GET /v3/accounts/{accountID}/pricing/stream?instruments=XAU_USD
        """
        if not self.is_configured():
            logger.info("OANDA credentials not set; skipping OANDA streaming.")
            return

        self._running = True
        self._stream_task = asyncio.create_task(self._stream_loop(callback, instrument))

    async def _stream_loop(
        self,
        callback: Callable[[float, float, float, int], Any],
        instrument: Optional[str] = None
    ):
        sym = instrument or self.settings.symbol
        url = f"{self.settings.stream_base_url}/accounts/{self.settings.account_id}/pricing/stream"
        params = {"instruments": sym}

        backoff = 1.0
        while self._running:
            try:
                logger.info("Connecting to OANDA v20 pricing stream for %s...", sym)
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream("GET", url, headers=self._get_headers(), params=params) as response:
                        if response.status_code == 200:
                            logger.info("Connected to OANDA v20 pricing stream.")
                            backoff = 1.0
                            async for line in response.aiter_lines():
                                if not self._running:
                                    break
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    msg = json.loads(line)
                                    if msg.get("type") == "PRICE":
                                        bids = msg.get("bids", [])
                                        asks = msg.get("asks", [])
                                        if bids and asks:
                                            bid = float(bids[0]["price"])
                                            ask = float(asks[0]["price"])
                                            price = round((bid + ask) / 2.0, 2)
                                            ts = parse_rfc3339_to_unix(msg.get("time", ""))
                                            res = callback(price, bid, ask, ts)
                                            if asyncio.iscoroutine(res):
                                                await res
                                except json.JSONDecodeError:
                                    continue
                        else:
                            logger.warning("OANDA pricing stream disconnected (HTTP %d)", response.status_code)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("OANDA stream connection interrupted: %s. Reconnecting in %.1fs...", e, backoff)

            if self._running:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)

    async def stop(self):
        """Stop background streaming task."""
        self._running = False
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass

    # =========================================================================
    # Account & Order Execution Management (Practice / Live)
    # =========================================================================
    async def get_account_summary(self) -> Optional[Dict[str, Any]]:
        """
        Fetch account summary including real-time balance and open position counts.
        Endpoint: GET /v3/accounts/{accountID}/summary
        """
        if not self.is_configured():
            return None

        url = f"{self.settings.rest_base_url}/accounts/{self.settings.account_id}/summary"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(url, headers=self._get_headers())
                if res.status_code == 200:
                    data = res.json()
                    return data.get("account", {})
                else:
                    logger.warning("OANDA get_account_summary HTTP %d: %s", res.status_code, res.text[:200])
        except Exception as e:
            logger.error("Error fetching OANDA account summary: %s", e)
        return None

    async def get_open_trades(self, instrument: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all active open trades for the instrument to ensure idempotency.
        Endpoint: GET /v3/accounts/{accountID}/openTrades
        """
        if not self.is_configured():
            return []

        url = f"{self.settings.rest_base_url}/accounts/{self.settings.account_id}/openTrades"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(url, headers=self._get_headers())
                if res.status_code == 200:
                    data = res.json()
                    trades = data.get("trades", [])
                    sym = instrument or self.settings.symbol
                    return [t for t in trades if t.get("instrument") == sym]
                else:
                    logger.warning("OANDA get_open_trades HTTP %d: %s", res.status_code, res.text[:200])
        except Exception as e:
            logger.error("Error fetching OANDA open trades: %s", e)
        return []

    async def create_order(
        self,
        units: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        entry_type: str = "MARKET",
        price: Optional[float] = None,
        instrument: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Submit a new market or limit order with bracket Stop Loss and Take Profit.
        Endpoint: POST /v3/accounts/{accountID}/orders
        """
        if not self.is_configured():
            logger.info("OANDA not configured; order creation skipped.")
            return None

        sym = instrument or self.settings.symbol
        url = f"{self.settings.rest_base_url}/accounts/{self.settings.account_id}/orders"

        # Units: positive for Buy/Long, negative for Sell/Short
        # Format units safely as integer string (e.g. 10 or -10 for standard XAU units)
        unit_str = str(int(round(units)))

        order_body: Dict[str, Any] = {
            "type": entry_type.upper(),
            "instrument": sym,
            "units": unit_str,
            "positionFill": "DEFAULT"
        }

        if entry_type.upper() == "MARKET":
            order_body["timeInForce"] = "FOK"
        elif entry_type.upper() == "LIMIT" and price:
            order_body["timeInForce"] = "GTC"
            order_body["price"] = f"{price:.2f}"

        if stop_loss is not None:
            order_body["stopLossOnFill"] = {
                "price": f"{stop_loss:.2f}",
                "timeInForce": "GTC"
            }

        if take_profit is not None:
            order_body["takeProfitOnFill"] = {
                "price": f"{take_profit:.2f}",
                "timeInForce": "GTC"
            }

        payload = {"order": order_body}

        try:
            logger.info("Submitting OANDA %s order: %s units of %s | SL: %s | TP: %s", entry_type, unit_str, sym, stop_loss, take_profit)
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=self._get_headers(), json=payload)
                if res.status_code in [200, 201]:
                    data = res.json()
                    logger.info("OANDA Order successfully filled/created: %s", data.get("orderFillTransaction", {}).get("id") or data.get("orderCreateTransaction", {}).get("id"))
                    return data
                else:
                    logger.error("OANDA order creation failed HTTP %d: %s", res.status_code, res.text)
        except Exception as e:
            logger.error("Exception during OANDA order submission: %s", e)
        return None

    async def update_trade_stop_loss(self, trade_id: str, stop_loss_price: float) -> bool:
        """
        Update the Stop Loss order on an active running trade (e.g. trail to Break-Even).
        Endpoint: PUT /v3/accounts/{accountID}/trades/{tradeID}/orders
        """
        if not self.is_configured():
            return False

        url = f"{self.settings.rest_base_url}/accounts/{self.settings.account_id}/trades/{trade_id}/orders"
        payload = {
            "stopLoss": {
                "price": f"{stop_loss_price:.2f}",
                "timeInForce": "GTC"
            }
        }

        try:
            logger.info("Updating OANDA Trade #%s Stop Loss to $%.2f", trade_id, stop_loss_price)
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.put(url, headers=self._get_headers(), json=payload)
                if res.status_code == 200:
                    logger.info("Successfully updated Stop Loss for Trade #%s", trade_id)
                    return True
                else:
                    logger.warning("Failed to update Stop Loss for Trade #%s HTTP %d: %s", trade_id, res.status_code, res.text[:200])
        except Exception as e:
            logger.error("Exception updating Stop Loss on OANDA: %s", e)
        return False

    async def close_trade(self, trade_id: str, units: Optional[str] = "ALL") -> bool:
        """
        Close an open trade by ID.
        Endpoint: PUT /v3/accounts/{accountID}/trades/{tradeID}/close
        """
        if not self.is_configured():
            return False

        url = f"{self.settings.rest_base_url}/accounts/{self.settings.account_id}/trades/{trade_id}/close"
        payload = {"units": units} if units else {}

        try:
            logger.info("Closing OANDA Trade #%s", trade_id)
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.put(url, headers=self._get_headers(), json=payload)
                if res.status_code == 200:
                    logger.info("Successfully closed Trade #%s on OANDA", trade_id)
                    return True
                else:
                    logger.warning("Failed to close Trade #%s HTTP %d: %s", trade_id, res.status_code, res.text[:200])
        except Exception as e:
            logger.error("Exception closing Trade #%s: %s", trade_id, e)
        return False
