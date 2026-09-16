"""
Real-Time Market Data Streamer and Multi-Timeframe Candle Aggregator.
Consumes live Gold spot feed (PAXGUSDT proxy) or simulated ticks, aggregates M1/M5/M15/H1,
calculates EMA 50 & EMA 200 for chart overlay, and compiles a comprehensive Quantitative Indicator Matrix
with actionable trading interpretations.
"""
import asyncio
import json
import logging
import random
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Callable, Any
import httpx
import numpy as np
import pandas as pd
import websockets

from src.config.settings import settings
from src.core.indicators import (
    Candle,
    calculate_ema,
    calculate_atr,
    calculate_adr,
    calculate_session_vwap,
    calculate_rsi,
    detect_rsi_divergence,
    resample_candles,
    calculate_bollinger_bands,
    calculate_macd,
    calculate_stochastic_rsi,
    calculate_obv,
    calculate_cmf,
    calculate_vwma,
    calculate_relative_volume,
    calculate_accumulation_distribution,
    calculate_pivot_points,
    calculate_order_flow_delta
)
from src.core.structure import (
    SessionLevels,
    FairValueGap,
    OrderBlock,
    calculate_session_levels,
    detect_liquidity_sweeps,
    detect_fair_value_gaps,
    detect_order_blocks,
    detect_break_of_structure,
    calculate_confluence_matrix
)
from src.core.setup_scanner import scan_market_setup, SetupResult
from src.integrations.macro_feed import MacroFeed
from src.integrations.economic_calendar import EconomicCalendar

logger = logging.getLogger(__name__)

DEFAULT_BASE_PRICE = 2935.00


class MarketDataEngine:
    """Coordinates real-time price feeds, multi-timeframe candle resampling, and rich indicator streaming."""

    def __init__(
        self,
        macro_feed: Optional[MacroFeed] = None,
        calendar: Optional[EconomicCalendar] = None
    ):
        self.macro_feed = macro_feed or MacroFeed()
        self.calendar = calendar or EconomicCalendar()

        # Rolling raw 1m candle history (stored as list of Candle objects)
        self._m1_candles: List[Candle] = []
        self._current_price: float = DEFAULT_BASE_PRICE
        self._bid: float = DEFAULT_BASE_PRICE - 0.10
        self._ask: float = DEFAULT_BASE_PRICE + 0.10
        self._spread: float = 0.20

        # Cached resampled dataframes for all timeframes
        self._m1_df: pd.DataFrame = pd.DataFrame()
        self._m5_df: pd.DataFrame = pd.DataFrame()
        self._m15_df: pd.DataFrame = pd.DataFrame()
        self._h1_df: pd.DataFrame = pd.DataFrame()
        self._h4_df: pd.DataFrame = pd.DataFrame()
        self._daily_df: pd.DataFrame = pd.DataFrame()

        # Cached indicator outputs
        self._vwap_series: pd.Series = pd.Series(dtype=float)
        self._vwap_upper1: pd.Series = pd.Series(dtype=float)
        self._vwap_upper2: pd.Series = pd.Series(dtype=float)
        self._vwap_lower1: pd.Series = pd.Series(dtype=float)
        self._vwap_lower2: pd.Series = pd.Series(dtype=float)
        self._fvgs_m5: List[FairValueGap] = []
        self._order_blocks_m5: List[OrderBlock] = []
        self._bos_m5: Optional[Dict[str, Any]] = None
        self._session_levels: SessionLevels = SessionLevels()
        self._confluence_matrix: Dict[str, Any] = {}
        self._volatility_state: Dict[str, Any] = {}
        self._indicators_matrix: Dict[str, Any] = {}
        self._mtf_summary: Dict[str, Any] = {}
        self._setup_result: SetupResult = SetupResult(
            grade="NO_SETUP",
            direction="NEUTRAL",
            confidence_score=0.0,
            setup_type="Initializing",
            timestamp=int(time.time())
        )

        # Listeners for real-time state broadcast
        self._listeners: Set[Callable[[Dict[str, Any]], Any]] = set()
        self._running: bool = False
        self._stream_task: Optional[asyncio.Task] = None
        self._tick_interval_task: Optional[asyncio.Task] = None

        # Pre-seed initial candle history
        self._seed_initial_history(base_price=DEFAULT_BASE_PRICE)

    def _seed_initial_history(self, num_bars: int = 2000, base_price: float = DEFAULT_BASE_PRICE):
        """Generate realistic initial candle history with realistic volatility and swings."""
        self._m1_candles.clear()
        now_ts = int(time.time())
        start_ts = now_ts - (num_bars * 60)
        
        current_p = base_price - 24.0
        for i in range(num_bars):
            ts = start_ts + (i * 60)
            wave = np.sin(i / 35.0) * 3.5 + np.cos(i / 14.0) * 1.5 + (i * (24.0 / num_bars))
            drift = random.gauss(0, 0.40)
            open_p = current_p
            close_p = open_p + (wave * 0.04) + drift
            
            bar_range = max(0.4, random.expovariate(1.0 / 1.2))
            high_p = max(open_p, close_p) + (bar_range * random.uniform(0.3, 0.7))
            low_p = min(open_p, close_p) - (bar_range * random.uniform(0.3, 0.7))
            vol = random.uniform(20.0, 180.0)

            self._m1_candles.append(Candle(
                timestamp=ts,
                open=round(open_p, 2),
                high=round(high_p, 2),
                low=round(low_p, 2),
                close=round(close_p, 2),
                volume=round(vol, 2)
            ))
            current_p = close_p

        self._current_price = round(current_p, 2)
        self._bid = round(self._current_price - 0.10, 2)
        self._ask = round(self._current_price + 0.10, 2)
        self._spread = round(self._ask - self._bid, 2)

        # Generate synthetic proportional higher timeframe series if offline
        now_ts = int(time.time())
        h4_bars = []
        h1_bars = []
        m15_bars = []
        for i in range(250, -1, -1):
            t_h4 = now_ts - (i * 14400)
            p_h4 = current_p + (i * random.uniform(-0.8, 0.8))
            h4_bars.append({'timestamp': t_h4, 'open': round(p_h4, 2), 'high': round(p_h4 + random.uniform(2.0, 6.0), 2), 'low': round(p_h4 - random.uniform(2.0, 6.0), 2), 'close': round(p_h4 + random.uniform(-1.0, 1.0), 2), 'volume': 2000.0})
        for i in range(300, -1, -1):
            t_h1 = now_ts - (i * 3600)
            p_h1 = current_p + (i * random.uniform(-0.4, 0.4))
            h1_bars.append({'timestamp': t_h1, 'open': round(p_h1, 2), 'high': round(p_h1 + random.uniform(1.0, 3.5), 2), 'low': round(p_h1 - random.uniform(1.0, 3.5), 2), 'close': round(p_h1 + random.uniform(-0.5, 0.5), 2), 'volume': 800.0})
        for i in range(300, -1, -1):
            t_m15 = now_ts - (i * 900)
            p_m15 = current_p + (i * random.uniform(-0.2, 0.2))
            m15_bars.append({'timestamp': t_m15, 'open': round(p_m15, 2), 'high': round(p_m15 + random.uniform(0.5, 1.5), 2), 'low': round(p_m15 - random.uniform(0.5, 1.5), 2), 'close': round(p_m15 + random.uniform(-0.3, 0.3), 2), 'volume': 200.0})

        self._h4_df = pd.DataFrame(h4_bars)
        self._h1_df = pd.DataFrame(h1_bars)
        self._m15_df = pd.DataFrame(m15_bars)

        self._seed_daily_history(self._current_price)
        self._recompute_all()

    def _seed_daily_history(self, current_price: float):
        """Generates realistic proportional daily history fallback if live D1 data is unavailable."""
        daily_records = []
        now_ts = int(time.time())
        day_start = now_ts - (now_ts % 86400)
        typical_half_range = current_price * 0.011
        for d in range(60, -1, -1):
            ts = day_start - (d * 86400)
            day_mid = current_price - (d * random.uniform(-2.0, 3.0))
            day_high = round(day_mid + random.uniform(typical_half_range * 0.8, typical_half_range * 1.3), 2)
            day_low = round(day_mid - random.uniform(typical_half_range * 0.8, typical_half_range * 1.3), 2)
            day_close = round(random.uniform(day_low + 5, day_high - 5), 2)
            day_open = round(random.uniform(day_low + 2, day_high - 2), 2)
            daily_records.append({
                'timestamp': ts,
                'open': day_open,
                'high': day_high,
                'low': day_low,
                'close': day_close,
                'volume': 50000.0
            })
        self._daily_df = pd.DataFrame(daily_records)

    async def _fetch_real_daily_history(self) -> bool:
        """Fetch actual historical Daily (1d) klines from public Binance REST API for accurate ADR calculation."""
        url = "https://api.binance.com/api/v3/klines?symbol=PAXGUSDT&interval=1d&limit=100"
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                res = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list) and len(data) >= 5:
                        records = []
                        for k in data:
                            records.append({
                                'timestamp': int(k[0]) // 1000,
                                'open': float(k[1]),
                                'high': float(k[2]),
                                'low': float(k[3]),
                                'close': float(k[4]),
                                'volume': float(k[5])
                            })
                        self._daily_df = pd.DataFrame(records)
                        logger.info("Successfully fetched %d real Daily (D1) klines for accurate ADR", len(records))
                        return True
            except Exception as e:
                logger.debug("Could not fetch daily klines: %s", e)
        return False

    async def _fetch_real_klines(self) -> bool:
        """Fetch actual historical MTF klines (1m, 15m, 1h, 4h, 1d) from Binance REST API."""
        base_urls = [
            "https://api.binance.com/api/v3/klines",
            "https://data-api.binance.vision/api/v3/klines"
        ]
        async with httpx.AsyncClient(timeout=6.0) as client:
            for base_url in base_urls:
                try:
                    # 1. Fetch 1m klines
                    res_1m = await client.get(f"{base_url}?symbol=PAXGUSDT&interval=1m&limit=1000", headers={"User-Agent": "Mozilla/5.0"})
                    if res_1m.status_code == 200:
                        data_1m = res_1m.json()
                        if isinstance(data_1m, list) and len(data_1m) >= 50:
                            candles = [
                                Candle(
                                    timestamp=int(k[0]) // 1000,
                                    open=float(k[1]),
                                    high=float(k[2]),
                                    low=float(k[3]),
                                    close=float(k[4]),
                                    volume=float(k[5])
                                ) for k in data_1m
                            ]
                            self._m1_candles = candles
                            self._current_price = round(candles[-1].close, 2)
                            self._bid = round(self._current_price - 0.10, 2)
                            self._ask = round(self._current_price + 0.10, 2)

                            # 2. Fetch H4 klines (500 bars ~ 83.3 days)
                            try:
                                res_h4 = await client.get(f"{base_url}?symbol=PAXGUSDT&interval=4h&limit=500", headers={"User-Agent": "Mozilla/5.0"})
                                if res_h4.status_code == 200:
                                    d_h4 = res_h4.json()
                                    if isinstance(d_h4, list) and len(d_h4) >= 10:
                                        self._h4_df = pd.DataFrame([
                                            {'timestamp': int(k[0]) // 1000, 'open': float(k[1]), 'high': float(k[2]), 'low': float(k[3]), 'close': float(k[4]), 'volume': float(k[5])}
                                            for k in d_h4
                                        ])
                            except Exception as e:
                                logger.debug("Could not fetch 4h klines: %s", e)

                            # 3. Fetch H1 klines (500 bars ~ 20.8 days)
                            try:
                                res_h1 = await client.get(f"{base_url}?symbol=PAXGUSDT&interval=1h&limit=500", headers={"User-Agent": "Mozilla/5.0"})
                                if res_h1.status_code == 200:
                                    d_h1 = res_h1.json()
                                    if isinstance(d_h1, list) and len(d_h1) >= 10:
                                        self._h1_df = pd.DataFrame([
                                            {'timestamp': int(k[0]) // 1000, 'open': float(k[1]), 'high': float(k[2]), 'low': float(k[3]), 'close': float(k[4]), 'volume': float(k[5])}
                                            for k in d_h1
                                        ])
                            except Exception as e:
                                logger.debug("Could not fetch 1h klines: %s", e)

                            # 4. Fetch M15 klines (500 bars ~ 5.2 days)
                            try:
                                res_m15 = await client.get(f"{base_url}?symbol=PAXGUSDT&interval=15m&limit=500", headers={"User-Agent": "Mozilla/5.0"})
                                if res_m15.status_code == 200:
                                    d_m15 = res_m15.json()
                                    if isinstance(d_m15, list) and len(d_m15) >= 10:
                                        self._m15_df = pd.DataFrame([
                                            {'timestamp': int(k[0]) // 1000, 'open': float(k[1]), 'high': float(k[2]), 'low': float(k[3]), 'close': float(k[4]), 'volume': float(k[5])}
                                            for k in d_m15
                                        ])
                            except Exception as e:
                                logger.debug("Could not fetch 15m klines: %s", e)

                            # 5. Fetch Daily (1d) klines (100 bars)
                            try:
                                res_1d = await client.get(f"{base_url}?symbol=PAXGUSDT&interval=1d&limit=100", headers={"User-Agent": "Mozilla/5.0"})
                                if res_1d.status_code == 200:
                                    d_1d = res_1d.json()
                                    if isinstance(d_1d, list) and len(d_1d) >= 10:
                                        self._daily_df = pd.DataFrame([
                                            {'timestamp': int(k[0]) // 1000, 'open': float(k[1]), 'high': float(k[2]), 'low': float(k[3]), 'close': float(k[4]), 'volume': float(k[5])}
                                            for k in d_1d
                                        ])
                            except Exception as e:
                                logger.debug("Could not fetch 1d klines: %s", e)

                            self._recompute_all()
                            logger.info("Successfully seeded MTF history: %d M1, %d M15, %d H1, %d H4, %d D1 bars", len(self._m1_candles), len(self._m15_df), len(self._h1_df), len(self._h4_df), len(self._daily_df))
                            return True
                except Exception as e:
                    logger.debug("Could not fetch klines from %s: %s", base_url, e)
        return False

    def _recompute_all(self):
        """Recompute resampled candles, indicators, structure levels, and detailed interpretation matrix across MTF."""
        if not self._m1_candles:
            return

        m1_df = pd.DataFrame([c.to_dict() for c in self._m1_candles])
        m1_df = m1_df.rename(columns={'time': 'timestamp'})
        self._m1_df = m1_df

        # Maintain rich multi-hundred bar histories across timeframes
        self._m5_df = resample_candles(m1_df, 5)
        
        if self._m15_df.empty or len(self._m15_df) <= 70:
            self._m15_df = resample_candles(m1_df, 15)
        elif not self._m15_df.empty:
            last_close = float(m1_df['close'].iloc[-1])
            self._m15_df.iloc[-1, self._m15_df.columns.get_loc('close')] = last_close
            self._m15_df.iloc[-1, self._m15_df.columns.get_loc('high')] = max(float(self._m15_df['high'].iloc[-1]), last_close)
            self._m15_df.iloc[-1, self._m15_df.columns.get_loc('low')] = min(float(self._m15_df['low'].iloc[-1]), last_close)

        if self._h1_df.empty or len(self._h1_df) <= 20:
            self._h1_df = resample_candles(m1_df, 60)
        elif not self._h1_df.empty:
            last_close = float(m1_df['close'].iloc[-1])
            self._h1_df.iloc[-1, self._h1_df.columns.get_loc('close')] = last_close
            self._h1_df.iloc[-1, self._h1_df.columns.get_loc('high')] = max(float(self._h1_df['high'].iloc[-1]), last_close)
            self._h1_df.iloc[-1, self._h1_df.columns.get_loc('low')] = min(float(self._h1_df['low'].iloc[-1]), last_close)

        if self._h4_df.empty or len(self._h4_df) <= 6:
            self._h4_df = resample_candles(m1_df, 240)
        elif not self._h4_df.empty:
            last_close = float(m1_df['close'].iloc[-1])
            self._h4_df.iloc[-1, self._h4_df.columns.get_loc('close')] = last_close
            self._h4_df.iloc[-1, self._h4_df.columns.get_loc('high')] = max(float(self._h4_df['high'].iloc[-1]), last_close)
            self._h4_df.iloc[-1, self._h4_df.columns.get_loc('low')] = min(float(self._h4_df['low'].iloc[-1]), last_close)

        # 1. EMAs across timeframes
        ema9_m5 = calculate_ema(self._m5_df['close'], min(9, len(self._m5_df))) if not self._m5_df.empty else pd.Series(dtype=float)
        ema20_m5 = calculate_ema(self._m5_df['close'], min(20, len(self._m5_df))) if not self._m5_df.empty else pd.Series(dtype=float)
        ema50_m5 = calculate_ema(self._m5_df['close'], min(50, len(self._m5_df))) if not self._m5_df.empty else pd.Series(dtype=float)
        ema200_m5 = calculate_ema(self._m5_df['close'], min(200, len(self._m5_df))) if not self._m5_df.empty else pd.Series(dtype=float)
        
        ema9_val = float(ema9_m5.iloc[-1]) if not ema9_m5.empty else None
        ema20_val = float(ema20_m5.iloc[-1]) if not ema20_m5.empty else None
        ema50_val = float(ema50_m5.iloc[-1]) if not ema50_m5.empty else None
        ema200_val = float(ema200_m5.iloc[-1]) if not ema200_m5.empty else None

        h1_ema200_val = None
        h1_rsi_val = None
        if len(self._h1_df) >= 5:
            h1_period = min(200, len(self._h1_df))
            h1_ema_series = calculate_ema(self._h1_df['close'], h1_period)
            h1_ema200_val = float(h1_ema_series.iloc[-1]) if not h1_ema_series.empty else None
            rsi_h1 = calculate_rsi(self._h1_df['close'], 14)
            h1_rsi_val = float(rsi_h1.iloc[-1]) if not rsi_h1.empty else None

        # 2. VWAP & RSI on M15 / M5
        m15_vwap_val = None
        m15_rsi_div = None
        rsi_m5_val = 50.0
        if len(self._m15_df) >= 5:
            vwap, u1, u2, l1, l2 = calculate_session_vwap(self._m15_df)
            self._vwap_series = vwap
            self._vwap_upper1 = u1
            self._vwap_upper2 = u2
            self._vwap_lower1 = l1
            self._vwap_lower2 = l2
            if not vwap.empty:
                m15_vwap_val = float(vwap.iloc[-1])
            
            rsi_m15 = calculate_rsi(self._m15_df['close'], 14)
            m15_rsi_div = detect_rsi_divergence(self._m15_df, rsi_m15)

        if len(self._m5_df) >= 14:
            s_rsi_m5 = calculate_rsi(self._m5_df['close'], 14)
            rsi_m5_val = round(float(s_rsi_m5.iloc[-1]), 1)

        # 3. Bollinger Bands & MACD & Stoch RSI
        bb_mid_val = None
        bb_up_val = None
        bb_low_val = None
        bb_bw_val = None
        if len(self._m5_df) >= 20:
            bb_mid, bb_up, bb_low, bb_bw = calculate_bollinger_bands(self._m5_df['close'], 20, 2.0)
            if not bb_mid.empty:
                bb_mid_val = round(float(bb_mid.iloc[-1]), 2)
                bb_up_val = round(float(bb_up.iloc[-1]), 2)
                bb_low_val = round(float(bb_low.iloc[-1]), 2)
                bb_bw_val = round(float(bb_bw.iloc[-1]), 2)

        macd_val = None
        macd_sig_val = None
        macd_hist_val = None
        if len(self._m5_df) >= 26:
            macd_l, macd_s, macd_h = calculate_macd(self._m5_df['close'], 12, 26, 9)
            if not macd_l.empty:
                macd_val = round(float(macd_l.iloc[-1]), 2)
                macd_sig_val = round(float(macd_s.iloc[-1]), 2)
                macd_hist_val = round(float(macd_h.iloc[-1]), 2)

        stoch_k_val = None
        stoch_d_val = None
        if len(self._m5_df) >= 28:
            s_k, s_d = calculate_stochastic_rsi(self._m5_df['close'], 14, 14, 3, 3)
            if not s_k.empty and not np.isnan(s_k.iloc[-1]):
                stoch_k_val = round(float(s_k.iloc[-1]), 1)
                stoch_d_val = round(float(s_d.iloc[-1]), 1)

        # 4. Volume Indicators (VWMA, OBV, CMF, RVol)
        vwma_m5_val = None
        cmf_m5_val = None
        latest_rvol = 1.0
        if len(self._m5_df) >= 20:
            vwma_m5 = calculate_vwma(self._m5_df, 20)
            if not vwma_m5.empty:
                vwma_m5_val = round(float(vwma_m5.iloc[-1]), 2)
            cmf_m5 = calculate_cmf(self._m5_df, 20)
            if not cmf_m5.empty:
                cmf_m5_val = round(float(cmf_m5.iloc[-1]), 3)
            _, latest_rvol = calculate_relative_volume(self._m5_df['volume'], 20)

        # 5. Volatility (ATR / ADR)
        atr_m5 = 2.20
        atr_m15 = 4.10
        atr_h1 = 8.50
        if len(self._m5_df) >= 10:
            s_atr_m5 = calculate_atr(self._m5_df, 14)
            if not s_atr_m5.empty and not s_atr_m5.isna().iloc[-1]:
                atr_m5 = round(float(s_atr_m5.iloc[-1]), 2)
        if len(self._m15_df) >= 10:
            s_atr_m15 = calculate_atr(self._m15_df, 14)
            if not s_atr_m15.empty and not s_atr_m15.isna().iloc[-1]:
                atr_m15 = round(float(s_atr_m15.iloc[-1]), 2)
        if len(self._h1_df) >= 10:
            s_atr_h1 = calculate_atr(self._h1_df, 14)
            if not s_atr_h1.empty and not s_atr_h1.isna().iloc[-1]:
                atr_h1 = round(float(s_atr_h1.iloc[-1]), 2)

        adr_total, adr_used, adr_used_pct = calculate_adr(self._daily_df, 14)
        self._volatility_state = {
            "adr_total": adr_total,
            "adr_used": adr_used,
            "adr_used_pct": adr_used_pct,
            "atr_m5": atr_m5,
            "atr_m15": atr_m15,
            "atr_h1": atr_h1,
            "bollinger": {
                "upper": bb_up_val,
                "middle": bb_mid_val,
                "lower": bb_low_val,
                "bandwidth_pct": bb_bw_val
            }
        }

        # 6. Structure & Liquidity
        self._session_levels = calculate_session_levels(self._m5_df, self._daily_df)
        sweep = detect_liquidity_sweeps(self._m5_df, self._session_levels)
        self._session_levels.recent_sweep = sweep
        self._fvgs_m5 = detect_fair_value_gaps(self._m5_df)
        self._order_blocks_m5 = detect_order_blocks(self._m5_df, self._current_price)
        self._bos_m5 = detect_break_of_structure(self._m5_df)

        # 7. Confluence Matrix
        self._confluence_matrix = calculate_confluence_matrix(
            current_price=self._current_price,
            h1_ema200=h1_ema200_val,
            h1_rsi=h1_rsi_val,
            m15_vwap=m15_vwap_val,
            m15_rsi_div=m15_rsi_div,
            m5_sweep=sweep,
            active_fvgs=self._fvgs_m5
        )

        # 8. Detailed Indicators Interpretation Matrix
        self._indicators_matrix = self._build_interpretations_matrix(
            price=self._current_price,
            ema9=ema9_val,
            ema20=ema20_val,
            ema50=ema50_val,
            ema200=ema200_val,
            vwap=m15_vwap_val,
            vwma=vwma_m5_val,
            cmf=cmf_m5_val,
            rvol=latest_rvol,
            rsi_m5=rsi_m5_val,
            rsi_div=m15_rsi_div,
            macd=macd_val,
            macd_sig=macd_sig_val,
            macd_hist=macd_hist_val,
            stoch_k=stoch_k_val,
            stoch_d=stoch_d_val,
            adr_pct=adr_used_pct,
            sweep=sweep,
            fvgs=self._fvgs_m5,
            order_blocks=self._order_blocks_m5,
            bos=self._bos_m5
        )

        # 9. Setup Scanner (5-point institutional confluence detection)
        news_status = self.calendar.get_next_event_status()
        self._setup_result = scan_market_setup(
            current_price=self._current_price,
            m5_df=self._m5_df,
            levels=self._session_levels,
            fvgs=self._fvgs_m5,
            m15_vwap=m15_vwap_val,
            h1_ema200=h1_ema200_val,
            adr_used_pct=adr_used_pct,
            news_guard_active=news_status.get("guard_active", False),
            atr_m5=atr_m5
        )

    def _build_interpretations_matrix(
        self,
        price: float,
        ema9: Optional[float],
        ema20: Optional[float],
        ema50: Optional[float],
        ema200: Optional[float],
        vwap: Optional[float],
        vwma: Optional[float],
        cmf: Optional[float],
        rvol: float,
        rsi_m5: float,
        rsi_div: Optional[str],
        macd: Optional[float],
        macd_sig: Optional[float],
        macd_hist: Optional[float],
        stoch_k: Optional[float],
        stoch_d: Optional[float],
        adr_pct: float,
        sweep: Optional[str],
        fvgs: List[FairValueGap],
        order_blocks: List[OrderBlock],
        bos: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compiles technical interpretations across trend, momentum, volume flow, and structure."""
        
        # 1. EMA Trend Interpretation
        ema_status = "NEUTRAL"
        ema_interp = "Price consolidating near moving averages."
        if ema50 and ema200:
            if price > ema50 > ema200:
                ema_status = "STRONG_BULLISH"
                ema_interp = f"Price > EMA50 (${ema50:.2f}) > EMA200 (${ema200:.2f}). Bullish trend alignment."
            elif price < ema50 < ema200:
                ema_status = "STRONG_BEARISH"
                ema_interp = f"Price < EMA50 (${ema50:.2f}) < EMA200 (${ema200:.2f}). Bearish trend alignment."
            elif price > ema200:
                ema_status = "MODERATE_BULLISH"
                ema_interp = f"Trading above Macro EMA200 (${ema200:.2f}). Pullback to EMA50 support."
            else:
                ema_status = "MODERATE_BEARISH"
                ema_interp = f"Trading below Macro EMA200 (${ema200:.2f}). Resistance near EMA50."

        # 2. VWAP Intraday Value Interpretation
        vwap_status = "NEUTRAL"
        vwap_interp = "Price floating near Session VWAP benchmark."
        if vwap:
            diff = price - vwap
            if diff > 1.50:
                vwap_status = "BULLISH_EXPANSION"
                vwap_interp = f"Above Session VWAP (${vwap:.2f}) by +${diff:.2f}. Intraday buyers in control."
            elif diff < -1.50:
                vwap_status = "BEARISH_EXPANSION"
                vwap_interp = f"Below Session VWAP (${vwap:.2f}) by -${abs(diff):.2f}. Intraday sellers dominant."
            else:
                vwap_status = "AT_VALUE"
                vwap_interp = f"Trading at fair value (${vwap:.2f}). Equilibrium zone."

        # 3. Volume & Money Flow (VWMA, CMF, RVol)
        volume_status = "NORMAL"
        vol_interp = f"RVol at {rvol:.1f}x. Standard volume participation."
        if rvol >= 2.0:
            volume_status = "VOLUME_CLIMAX"
            vol_interp = f"⚠️ High Volume Spike ({rvol:.1f}x average). Institutional participation active."
        if cmf is not None:
            if cmf > 0.10:
                vol_interp += f" CMF (+{cmf:.2f}) indicates institutional accumulation."
            elif cmf < -0.10:
                vol_interp += f" CMF ({cmf:.2f}) indicates institutional distribution."

        # 4. Momentum & Oscillators (RSI, MACD, Stoch RSI)
        rsi_status = "NEUTRAL"
        rsi_interp = f"RSI(14) at {rsi_m5:.1f} (Balanced momentum zone 30-70)."
        if rsi_m5 >= 70.0:
            rsi_status = "OVERBOUGHT"
            rsi_interp = f"RSI(14) at {rsi_m5:.1f}. Overextended upside; caution on breakout chasing."
        elif rsi_m5 <= 30.0:
            rsi_status = "OVERSOLD"
            rsi_interp = f"RSI(14) at {rsi_m5:.1f}. Overextended downside; watch for relief bounce."
        
        if rsi_div:
            rsi_status += f" + {rsi_div}"
            if "BULLISH" in rsi_div:
                rsi_interp += " 🟢 Bullish divergence confirmed (momentum reversal trigger)."
            elif "BEARISH" in rsi_div:
                rsi_interp += " 🔴 Bearish divergence confirmed (exhaustion reversal trigger)."

        # 5. Structure & Liquidity Interpretation
        struct_status = "WAITING"
        struct_interp = "Monitoring session boundary interactions and liquidity pools."
        if sweep == "ASIA_LOW_SWEPT":
            struct_status = "BULLISH_SWEEP"
            struct_interp = "🟢 Asia Low swept and rejected! Liquidity purged; institutional buy trigger active."
        elif sweep == "ASIA_HIGH_SWEPT":
            struct_status = "BEARISH_SWEEP"
            struct_interp = "🔴 Asia High swept and rejected! Liquidity purged; institutional sell trigger active."
        elif sweep == "PDL_SWEPT":
            struct_status = "BULLISH_PDL_SWEEP"
            struct_interp = "🟢 Previous Day Low swept and rejected. Key daily demand level defended."
        elif sweep == "PDH_SWEPT":
            struct_status = "BEARISH_PDH_SWEEP"
            struct_interp = "🔴 Previous Day High swept and rejected. Key daily supply level held."

        if bos:
            struct_interp += f" | {bos.get('interpretation', '')}"

        # 6. Fair Value Gaps & Order Blocks
        fvg_interp = "No active unmitigated FVG nearby."
        for g in reversed(fvgs):
            if not g.mitigated:
                fvg_interp = f"Active {g.type} FVG at [${g.bottom:.2f} - ${g.top:.2f}]. Imbalance magnet zone."
                break

        return {
            "ema": {
                "status": ema_status,
                "ema9": round(ema9, 2) if ema9 else None,
                "ema20": round(ema20, 2) if ema20 else None,
                "ema50": round(ema50, 2) if ema50 else None,
                "ema200": round(ema200, 2) if ema200 else None,
                "interpretation": ema_interp
            },
            "vwap": {
                "status": vwap_status,
                "value": round(vwap, 2) if vwap else None,
                "vwma": round(vwma, 2) if vwma else None,
                "interpretation": vwap_interp
            },
            "volume_flow": {
                "status": volume_status,
                "rvol": rvol,
                "cmf": cmf,
                "interpretation": vol_interp
            },
            "rsi": {
                "status": rsi_status,
                "value": rsi_m5,
                "divergence": rsi_div,
                "interpretation": rsi_interp
            },
            "macd": {
                "line": macd,
                "signal": macd_sig,
                "histogram": macd_hist
            },
            "stochastic_rsi": {
                "k": stoch_k,
                "d": stoch_d
            },
            "adr": {
                "status": "NORMAL" if adr_pct < 80 else "EXHAUSTED",
                "pct_used": adr_pct,
                "interpretation": f"{adr_pct:.1f}% ADR used today."
            },
            "structure": {
                "status": struct_status,
                "sweep": sweep,
                "bos": bos,
                "interpretation": struct_interp
            },
            "fvg": {
                "interpretation": fvg_interp
            }
        }

    def process_tick(
        self,
        price: float,
        volume: float = 1.0,
        timestamp: Optional[int] = None,
        spread: Optional[float] = None,
        bid: Optional[float] = None,
        ask: Optional[float] = None
    ):
        """Process incoming live price tick and update M1 candle."""
        if price <= 0:
            return

        if self._current_price > 0 and abs(price - self._current_price) / self._current_price > 0.05:
            logger.info("Re-anchoring historical candles to live price level: %.2f", price)
            self._seed_initial_history(base_price=price)

        now_ts = timestamp or int(time.time())
        minute_ts = now_ts - (now_ts % 60)

        self._current_price = round(price, 2)
        if spread is not None:
            self._spread = round(spread, 2)
        elif bid is not None and ask is not None:
            self._spread = round(ask - bid, 2)
        else:
            self._spread = round(random.uniform(0.15, 0.25), 2)

        self._bid = round(bid if bid is not None else self._current_price - (self._spread / 2.0), 2)
        self._ask = round(ask if ask is not None else self._current_price + (self._spread / 2.0), 2)

        if not self._m1_candles or self._m1_candles[-1].timestamp < minute_ts:
            new_candle = Candle(
                timestamp=minute_ts,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume
            )
            self._m1_candles.append(new_candle)
            if len(self._m1_candles) > settings.market.max_history_bars:
                self._m1_candles.pop(0)
        else:
            curr = self._m1_candles[-1]
            curr.high = max(curr.high, price)
            curr.low = min(curr.low, price)
            curr.close = price
            curr.volume += volume

        self._recompute_all()

    def get_state_frame(self) -> Dict[str, Any]:
        """Builds unified real-time dashboard payload conforming to architecture spec."""
        now_ts = int(time.time())
        candle_timer_m5 = 300 - (now_ts % 300)

        macro_data = self.macro_feed.get_state()
        news_status = self.calendar.get_next_event_status()
        fvgs_data = [g.to_dict() for g in self._fvgs_m5]
        obs_data = [b.to_dict() for b in self._order_blocks_m5]

        # Multi-Timeframe RSI
        m1_rsi = 50.0
        m15_rsi = 50.0
        h1_rsi = 50.0
        h4_rsi = 50.0
        if len(self._m1_df) >= 14:
            s_r = calculate_rsi(self._m1_df['close'], 14)
            if not s_r.empty and not pd.isna(s_r.iloc[-1]):
                m1_rsi = round(float(s_r.iloc[-1]), 1)
        if len(self._m15_df) >= 14:
            s_r = calculate_rsi(self._m15_df['close'], 14)
            if not s_r.empty and not pd.isna(s_r.iloc[-1]):
                m15_rsi = round(float(s_r.iloc[-1]), 1)
        if len(self._h1_df) >= 14:
            s_r = calculate_rsi(self._h1_df['close'], 14)
            if not s_r.empty and not pd.isna(s_r.iloc[-1]):
                h1_rsi = round(float(s_r.iloc[-1]), 1)
        
        if len(self._h4_df) >= 14:
            s_r = calculate_rsi(self._h4_df['close'], 14)
            if not s_r.empty and not pd.isna(s_r.iloc[-1]):
                h4_rsi = round(float(s_r.iloc[-1]), 1)
        elif not self._daily_df.empty:
            daily_closes = self._daily_df['close'].tolist()
            h4_closes = self._h4_df['close'].tolist() if not self._h4_df.empty else [self._current_price]
            combined = pd.Series(daily_closes + h4_closes)
            s_r = calculate_rsi(combined, 14)
            if not s_r.empty and not pd.isna(s_r.iloc[-1]):
                h4_rsi = round(float(s_r.iloc[-1]), 1)

        multi_tf_rsi = {
            "M1": {"val": m1_rsi, "tag": "▲" if m1_rsi >= 55 else ("▼" if m1_rsi <= 45 else "─")},
            "M15": {"val": m15_rsi, "tag": "▲" if m15_rsi >= 55 else ("▼" if m15_rsi <= 45 else "─")},
            "H1": {"val": h1_rsi, "tag": "▲" if h1_rsi >= 55 else ("▼" if h1_rsi <= 45 else "─")},
            "H4": {"val": h4_rsi, "tag": "▲" if h4_rsi >= 55 else ("▼" if h4_rsi <= 45 else "─")}
        }

        # Standard Floor Pivot Points
        pivots = calculate_pivot_points(self._daily_df, self._current_price)

        # Order Flow Delta (Unified 30m rolling source of truth)
        order_flow = calculate_order_flow_delta(self._m1_candles)

        # Daily Range (High, Low, Change %)
        day_open = self._current_price
        day_high = self._current_price
        day_low = self._current_price
        if not self._daily_df.empty:
            last_d = self._daily_df.iloc[-1]
            day_open = float(last_d.get('open', self._current_price))
            day_high = max(float(last_d.get('high', self._current_price)), self._current_price)
            day_low = min(float(last_d.get('low', self._current_price)), self._current_price)
        elif self._m1_candles:
            day_open = self._m1_candles[0].open
            day_high = max(c.high for c in self._m1_candles)
            day_low = min(c.low for c in self._m1_candles)

        chg_pct = round(((self._current_price - day_open) / day_open) * 100.0, 2) if day_open > 0 else 0.0

        daily_range = {
            "open": round(day_open, 2),
            "high": round(day_high, 2),
            "low": round(day_low, 2),
            "change_pct": chg_pct,
            "today_range": round(day_high - day_low, 2)
        }

        # Sub-pills for each of the 4 charts (Tailored directly to each panel's native timeframe)
        vwap_val = round(self._indicators_matrix.get("vwap", {}).get("value") or self._current_price, 2)
        
        # M1 native EMA 9
        ema9_m1 = calculate_ema(self._m1_df['close'], min(9, len(self._m1_df))) if not self._m1_df.empty else pd.Series(dtype=float)
        ema9_m1_val = round(float(ema9_m1.iloc[-1]), 2) if not ema9_m1.empty else round(self._current_price, 2)

        # M15 native EMA 9 and EMA 21
        ema9_m15 = calculate_ema(self._m15_df['close'], min(9, len(self._m15_df))) if not self._m15_df.empty else pd.Series(dtype=float)
        ema21_m15 = calculate_ema(self._m15_df['close'], min(21, len(self._m15_df))) if not self._m15_df.empty else pd.Series(dtype=float)
        ema9_m15_val = round(float(ema9_m15.iloc[-1]), 2) if not ema9_m15.empty else round(self._current_price, 2)
        ema21_m15_val = round(float(ema21_m15.iloc[-1]), 2) if not ema21_m15.empty else round(self._current_price, 2)

        # H1 native EMA 50 and EMA 200
        ema50_h1 = calculate_ema(self._h1_df['close'], min(50, len(self._h1_df))) if not self._h1_df.empty else pd.Series(dtype=float)
        ema200_h1 = calculate_ema(self._h1_df['close'], min(200, len(self._h1_df))) if not self._h1_df.empty else pd.Series(dtype=float)
        ema50_h1_val = round(float(ema50_h1.iloc[-1]), 2) if not ema50_h1.empty else round(self._current_price, 2)
        ema200_h1_val = round(float(ema200_h1.iloc[-1]), 2) if not ema200_h1.empty else round(self._current_price, 2)

        # H4 native EMA 50 and EMA 200
        ema50_h4 = calculate_ema(self._h4_df['close'], min(50, len(self._h4_df))) if not self._h4_df.empty else pd.Series(dtype=float)
        ema200_h4 = calculate_ema(self._h4_df['close'], min(200, len(self._h4_df))) if not self._h4_df.empty else pd.Series(dtype=float)
        ema50_h4_val = round(float(ema50_h4.iloc[-1]), 2) if not ema50_h4.empty else round(self._current_price, 2)
        ema200_h4_val = round(float(ema200_h4.iloc[-1]), 2) if not ema200_h4.empty else round(self._current_price, 2)

        atr_h1 = self._volatility_state.get("atr_h1", 4.80)
        atr_h4 = round(atr_h1 * 2.2, 2)

        chart_pills = {
            "m1": {
                "ema9": ema9_m1_val,
                "vwap": vwap_val,
                "order_flow": f"{order_flow['formatted']}"
            },
            "m15": {
                "ema9": ema9_m15_val,
                "ema21": ema21_m15_val,
                "range": round(daily_range["high"] - daily_range["low"], 2)
            },
            "h1": {
                "ema50": ema50_h1_val,
                "ema200": ema200_h1_val,
                "pp": pivots["pp"],
                "atr14": atr_h1
            },
            "h4": {
                "ema50": ema50_h4_val,
                "ema200": ema200_h4_val,
                "sweep": self._session_levels.recent_sweep or f"Low @ ${pivots['s1']:.2f}",
                "atr14": atr_h4
            }
        }

        spread_pips = round(self._spread / 0.10, 1)
        spread_formatted = f"${self._spread:.2f} ({spread_pips:.1f} pips)"

        return {
            "timestamp": now_ts,
            "xauusd": {
                "price": self._current_price,
                "bid": self._bid,
                "ask": self._ask,
                "spread": round(self._spread, 2),
                "spread_pips": spread_pips,
                "spread_formatted": spread_formatted,
                "change_pct": chg_pct,
                "volume_status": self._indicators_matrix.get("volume_flow", {}).get("status", "NORMAL"),
                "candle_timer_m5": candle_timer_m5,
                "timestamp": now_ts
            },
            "macro": macro_data,
            "confluence_matrix": self._confluence_matrix,
            "indicators_matrix": self._indicators_matrix,
            "volatility": self._volatility_state,
            "session": self._session_levels.to_dict(),
            "news": news_status,
            "setup_scan": self._setup_result.to_dict(),
            "pivots": pivots,
            "order_flow": order_flow,
            "multi_tf_rsi": multi_tf_rsi,
            "daily_range": daily_range,
            "chart_pills": chart_pills,
            "overlays": {
                "fvgs": fvgs_data,
                "order_blocks": obs_data,
                "bos": self._bos_m5
            }
        }

    def get_history(self, timeframe: str = "M5") -> List[Dict[str, Any]]:
        """Retrieve historical candles and indicator overlays for any requested timeframe (M1, M5, M15, H1, H4, D1)."""
        tf = timeframe.upper()
        if tf in ["H4", "240"]:
            df = self._h4_df if not self._h4_df.empty else (resample_candles(self._m1_df, 240) if not self._m1_df.empty else pd.DataFrame())
        elif tf in ["H1", "60"]:
            df = self._h1_df if not self._h1_df.empty else (resample_candles(self._m1_df, 60) if not self._m1_df.empty else pd.DataFrame())
        elif tf in ["M15", "15"]:
            df = self._m15_df if not self._m15_df.empty else (resample_candles(self._m1_df, 15) if not self._m1_df.empty else pd.DataFrame())
        elif tf in ["M1", "1"]:
            df = self._m1_df if not self._m1_df.empty else (pd.DataFrame([c.to_dict() for c in self._m1_candles]).rename(columns={'time': 'timestamp'}) if self._m1_candles else pd.DataFrame())
        elif tf in ["D1", "D", "1440"]:
            df = self._daily_df if not self._daily_df.empty else (resample_candles(self._m1_df, 1440) if not self._m1_df.empty else pd.DataFrame())
        else:
            df = self._m5_df if not self._m5_df.empty else (resample_candles(self._m1_df, 5) if not self._m1_df.empty else pd.DataFrame())

        if df.empty and self._m1_candles:
            self._recompute_all()
            if tf in ["H4", "240"]: df = self._h4_df
            elif tf in ["H1", "60"]: df = self._h1_df
            elif tf in ["M15", "15"]: df = self._m15_df
            elif tf in ["M1", "1"]: df = self._m1_df
            elif tf in ["D1", "D", "1440"]: df = self._daily_df
            else: df = self._m5_df

        if df.empty:
            return []

        # Calculate EMAs (9, 20, 50, 200), VWMA (20), Bollinger Bands (20, 2), VWAP
        n = len(df)
        ema9 = calculate_ema(df['close'], min(9, n))
        ema20 = calculate_ema(df['close'], min(20, n))
        ema50 = calculate_ema(df['close'], min(50, n))
        ema200 = calculate_ema(df['close'], min(200, n))
        vwma20 = calculate_vwma(df, min(20, n)) if 'volume' in df.columns else pd.Series(dtype=float)
        bb_mid, bb_up, bb_low, _ = calculate_bollinger_bands(df['close'], min(20, n), 2.0)
        vwap_s, vwap_u1, vwap_u2, vwap_l1, vwap_l2 = calculate_session_vwap(df) if n >= 5 else (pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float))

        records = []
        for i, row in df.iterrows():
            e9_val = round(float(ema9.iloc[i]), 2) if not ema9.empty and not np.isnan(ema9.iloc[i]) else None
            e20_val = round(float(ema20.iloc[i]), 2) if not ema20.empty and not np.isnan(ema20.iloc[i]) else None
            e50_val = round(float(ema50.iloc[i]), 2) if not ema50.empty and not np.isnan(ema50.iloc[i]) else None
            e200_val = round(float(ema200.iloc[i]), 2) if not ema200.empty and not np.isnan(ema200.iloc[i]) else None
            vwma_val = round(float(vwma20.iloc[i]), 2) if not vwma20.empty and not np.isnan(vwma20.iloc[i]) else None
            bb_u = round(float(bb_up.iloc[i]), 2) if not bb_up.empty and not np.isnan(bb_up.iloc[i]) else None
            bb_m = round(float(bb_mid.iloc[i]), 2) if not bb_mid.empty and not np.isnan(bb_mid.iloc[i]) else None
            bb_l = round(float(bb_low.iloc[i]), 2) if not bb_low.empty and not np.isnan(bb_low.iloc[i]) else None
            
            vwap_val = round(float(vwap_s.iloc[i]), 2) if not vwap_s.empty and not np.isnan(vwap_s.iloc[i]) else None
            vwap_u1_val = round(float(vwap_u1.iloc[i]), 2) if not vwap_u1.empty and not np.isnan(vwap_u1.iloc[i]) else None
            vwap_u2_val = round(float(vwap_u2.iloc[i]), 2) if not vwap_u2.empty and not np.isnan(vwap_u2.iloc[i]) else None
            vwap_l1_val = round(float(vwap_l1.iloc[i]), 2) if not vwap_l1.empty and not np.isnan(vwap_l1.iloc[i]) else None
            vwap_l2_val = round(float(vwap_l2.iloc[i]), 2) if not vwap_l2.empty and not np.isnan(vwap_l2.iloc[i]) else None

            ts_val = int(row['timestamp']) if 'timestamp' in row and not pd.isna(row['timestamp']) else int(time.time() - (n - 1 - i) * 300)
            open_val = round(float(row['open']), 2) if 'open' in row and not pd.isna(row['open']) else round(float(row['close']), 2)

            records.append({
                "time": ts_val,
                "timestamp": ts_val,
                "open": open_val,
                "high": round(float(row['high']), 2),
                "low": round(float(row['low']), 2),
                "close": round(float(row['close']), 2),
                "volume": round(float(row['volume']), 2),
                "ema9": e9_val,
                "ema20": e20_val,
                "ema50": e50_val,
                "ema200": e200_val,
                "vwma20": vwma_val,
                "bb_upper": bb_u,
                "bb_middle": bb_m,
                "bb_lower": bb_l,
                "vwap": vwap_val,
                "vwap_upper_1": vwap_u1_val,
                "vwap_upper_2": vwap_u2_val,
                "vwap_lower_1": vwap_l1_val,
                "vwap_lower_2": vwap_l2_val
            })
        return records

    def add_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        self._listeners.add(callback)

    def remove_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        self._listeners.discard(callback)

    async def _notify_listeners(self):
        state = self.get_state_frame()
        for listener in list(self._listeners):
            try:
                res = listener(state)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.debug("Error notifying listener: %s", e)

    async def start(self):
        """Start live market streaming."""
        self._running = True
        await self.macro_feed.start()
        
        # 1. Warm up daily history & klines
        try:
            await self._fetch_real_daily_history()
            await self._fetch_real_klines()
        except Exception as e:
            logger.debug("History warm-up fetch: %s", e)

        if self._daily_df.empty:
            self._seed_daily_history(self._current_price)

        # 2. Start Binance Public WebSocket Stream (100% real live market ticks)
        self._stream_task = asyncio.create_task(self._binance_ws_loop())

    async def stop(self):
        """Stop background tasks."""
        self._running = False
        await self.macro_feed.stop()
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()

    async def _binance_ws_loop(self):
        """Connects to Binance public websocket for live Gold spot proxy."""
        url = settings.market.binance_ticker_ws_url
        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("Connected to live market data stream.")
                    while self._running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        if 'c' in data:
                            price = float(data['c'])
                            vol = float(data.get('v', 1.0))
                            self.process_tick(price, vol)
                            await self._notify_listeners()
            except Exception as e:
                logger.debug("External market stream reconnecting in %ss (%s)", settings.market.reconnect_delay_seconds, e)
                await asyncio.sleep(settings.market.reconnect_delay_seconds)
