"""
Core Quantitative Analytics Engine for XAUUSD Multi-Timeframe Dashboard.
Calculates VWAP, standard deviation bands, EMAs (20, 50, 200), ATR, ADR, and RSI Divergence.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd


@dataclass
class Candle:
    """Represents a single OHLCV candlestick."""
    timestamp: int  # Unix timestamp in seconds
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time": self.timestamp,
            "open": round(self.open, 2),
            "high": round(self.high, 2),
            "low": round(self.low, 2),
            "close": round(self.close, 2),
            "volume": round(self.volume, 2),
        }


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average (EMA) for a given period."""
    if len(series) < period or series.empty:
        return pd.Series(index=series.index, dtype=float)
    return series.ewm(span=period, adjust=False).mean()


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR).
    Requires 'high', 'low', 'close' columns in DataFrame.
    """
    if len(df) < 2:
        return pd.Series(np.nan, index=df.index)

    high = df['high']
    low = df['low']
    close_prev = df['close'].shift(1)

    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Wilder's Smoothing / RMA for ATR
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return atr


def calculate_adr(daily_df: pd.DataFrame, period: int = 14) -> Tuple[float, float, float]:
    """
    Calculate Average Daily Range (ADR).
    Returns (adr_total, current_day_range, adr_used_pct).
    """
    if daily_df.empty or len(daily_df) < 1:
        return (0.0, 0.0, 0.0)

    daily_ranges = daily_df['high'] - daily_df['low']
    
    # Calculate average over past 'period' completed days if available
    if len(daily_ranges) > 1:
        adr_total = float(daily_ranges.iloc[:-1].tail(period).mean())
    else:
        adr_total = float(daily_ranges.iloc[0])

    if adr_total <= 0:
        adr_total = 30.0  # Safe default for Gold if not enough history

    current_day_range = float(daily_ranges.iloc[-1])
    adr_used_pct = round(min((current_day_range / adr_total) * 100.0, 300.0), 1)

    return (round(adr_total, 2), round(current_day_range, 2), adr_used_pct)


def calculate_session_vwap(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Calculate Session VWAP (Volume Weighted Average Price) with standard deviation bands:
    - Session VWAP
    - +1 Standard Deviation Band
    - +2 Standard Deviation Band
    - -1 Standard Deviation Band
    - -2 Standard Deviation Band
    
    Session resets daily at 00:00 UTC.
    """
    if df.empty:
        empty = pd.Series(dtype=float)
        return empty, empty, empty, empty, empty

    df_copy = df.copy()
    if 'timestamp' in df_copy.columns:
        dt_series = pd.to_datetime(df_copy['timestamp'], unit='s', utc=True)
    elif isinstance(df_copy.index, pd.DatetimeIndex):
        dt_series = df_copy.index
    else:
        dt_series = pd.Series(pd.to_datetime('now', utc=True), index=df_copy.index)

    typical_price = (df_copy['high'] + df_copy['low'] + df_copy['close']) / 3.0
    volume = df_copy['volume'].replace(0, 1.0)  # Avoid div by zero

    # Group by UTC date for session reset
    dates = dt_series.dt.date if hasattr(dt_series, 'dt') else pd.Series(dt_series).dt.date
    
    pv = typical_price * volume
    pv_cumsum = pv.groupby(dates).cumsum()
    vol_cumsum = volume.groupby(dates).cumsum()

    vwap = pv_cumsum / vol_cumsum

    # VWAP Standard Deviation: sqrt( sum(vol * (tp - vwap)^2) / sum(vol) )
    sq_diff = (typical_price - vwap) ** 2
    sq_diff_pv = sq_diff * volume
    sq_diff_cumsum = sq_diff_pv.groupby(dates).cumsum()
    variance = (sq_diff_cumsum / vol_cumsum).clip(lower=0)
    std_dev = np.sqrt(variance)

    upper_1 = vwap + std_dev
    upper_2 = vwap + (2.0 * std_dev)
    lower_1 = vwap - std_dev
    lower_2 = vwap - (2.0 * std_dev)

    return vwap, upper_1, upper_2, lower_1, lower_2


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index (RSI) using Wilder's RMA smoothing."""
    if len(series) < period + 1:
        return pd.Series(50.0, index=series.index)

    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, 1e-9)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def detect_rsi_divergence(
    candles_df: pd.DataFrame,
    rsi_series: pd.Series,
    lookback: int = 15,
    order: int = 3
) -> Optional[str]:
    """
    Detect Regular and Hidden RSI Divergences over a recent swing lookback window.
    Returns:
    - 'REGULAR_BULLISH' (Lower Low in Price, Higher Low in RSI)
    - 'REGULAR_BEARISH' (Higher High in Price, Lower High in RSI)
    - 'HIDDEN_BULLISH'  (Higher Low in Price, Lower Low in RSI - Trend Continuation)
    - 'HIDDEN_BEARISH'  (Lower High in Price, Higher High in RSI - Trend Continuation)
    - None if no divergence confirmed
    """
    if len(candles_df) < lookback + order * 2 or len(rsi_series) < lookback:
        return None

    close = candles_df['close'].tail(lookback).values
    low = candles_df['low'].tail(lookback).values
    high = candles_df['high'].tail(lookback).values
    rsi = rsi_series.tail(lookback).values

    # Find swing lows
    swing_lows = []
    for i in range(order, len(low) - order):
        if low[i] == min(low[i - order: i + order + 1]):
            swing_lows.append((i, low[i], rsi[i]))

    # Find swing highs
    swing_highs = []
    for i in range(order, len(high) - order):
        if high[i] == max(high[i - order: i + order + 1]):
            swing_highs.append((i, high[i], rsi[i]))

    # Check Bullish Divergence on swing lows
    if len(swing_lows) >= 2:
        prev_idx, prev_price_low, prev_rsi = swing_lows[-2]
        curr_idx, curr_price_low, curr_rsi = swing_lows[-1]

        if curr_price_low < prev_price_low and curr_rsi > prev_rsi + 1.5:
            return "REGULAR_BULLISH"
        elif curr_price_low > prev_price_low and curr_rsi < prev_rsi - 1.5:
            return "HIDDEN_BULLISH"

    # Check Bearish Divergence on swing highs
    if len(swing_highs) >= 2:
        prev_idx, prev_price_high, prev_rsi = swing_highs[-2]
        curr_idx, curr_price_high, curr_rsi = swing_highs[-1]

        if curr_price_high > prev_price_high and curr_rsi < prev_rsi - 1.5:
            return "REGULAR_BEARISH"
        elif curr_price_high < prev_price_high and curr_rsi > prev_rsi + 1.5:
            return "HIDDEN_BEARISH"

    return None


def resample_candles(df_1m: pd.DataFrame, timeframe_minutes: int) -> pd.DataFrame:
    """
    Resample 1-minute OHLCV candles to target timeframe (e.g. 5, 15, 60 minutes).
    """
    if df_1m.empty:
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    df = df_1m.copy()
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
    df = df.set_index('dt')

    rule = f"{timeframe_minutes}min" if timeframe_minutes < 60 else "1h"
    resampled = df.resample(rule, closed='left', label='left').agg({
        'timestamp': 'first',
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()

    resampled['timestamp'] = resampled['timestamp'].astype(int)
    return resampled.reset_index(drop=True)
