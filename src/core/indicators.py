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


def calculate_bollinger_bands(
    series: pd.Series,
    period: int = 20,
    num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands (Middle SMA, Upper Band, Lower Band, Bandwidth %).
    """
    if len(series) < period or series.empty:
        empty = pd.Series(index=series.index, dtype=float)
        return empty, empty, empty, empty

    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = middle + (num_std * std)
    lower = middle - (num_std * std)
    bandwidth_pct = ((upper - lower) / middle.replace(0, 1e-9)) * 100.0

    return middle, upper, lower, bandwidth_pct


def calculate_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Moving Average Convergence Divergence (MACD).
    Returns (macd_line, signal_line, histogram).
    """
    if len(series) < slow or series.empty:
        empty = pd.Series(index=series.index, dtype=float)
        return empty, empty, empty

    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def calculate_stochastic_rsi(
    series: pd.Series,
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_period: int = 3,
    d_period: int = 3
) -> Tuple[pd.Series, pd.Series]:
    """
    Calculate Stochastic RSI (%K, %D).
    """
    if len(series) < rsi_period + stoch_period:
        empty = pd.Series(index=series.index, dtype=float)
        return empty, empty

    rsi = calculate_rsi(series, period=rsi_period)
    min_rsi = rsi.rolling(window=stoch_period).min()
    max_rsi = rsi.rolling(window=stoch_period).max()
    denom = (max_rsi - min_rsi).replace(0, 1e-9)

    stoch_raw = ((rsi - min_rsi) / denom) * 100.0
    k_line = stoch_raw.rolling(window=k_period).mean()
    d_line = k_line.rolling(window=d_period).mean()

    return k_line, d_line


# ==============================================================================
# Volume-Based Indicators
# ==============================================================================

def calculate_obv(df: pd.DataFrame) -> pd.Series:
    """
    Calculate On-Balance Volume (OBV).
    Cumulative volume based on close-to-close directional change.
    """
    if df.empty or 'close' not in df.columns or 'volume' not in df.columns:
        return pd.Series(dtype=float)

    delta = df['close'].diff()
    direction = np.where(delta > 0, 1.0, np.where(delta < 0, -1.0, 0.0))
    obv = (pd.Series(direction, index=df.index) * df['volume']).cumsum()
    return obv


def calculate_cmf(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Calculate Chaikin Money Flow (CMF).
    Measures institutional accumulation/distribution over 'period' bars.
    Returns values between -1.0 (heavy distribution) and +1.0 (heavy accumulation).
    """
    if len(df) < period or df.empty:
        return pd.Series(0.0, index=df.index)

    high = df['high']
    low = df['low']
    close = df['close']
    volume = df['volume']

    hl_range = (high - low).replace(0, 1e-9)
    # Money Flow Multiplier: [(Close - Low) - (High - Close)] / (High - Low)
    mfm = ((close - low) - (high - close)) / hl_range
    mf_volume = mfm * volume

    cmf = mf_volume.rolling(window=period).sum() / volume.rolling(window=period).sum().replace(0, 1e-9)
    return cmf.clip(lower=-1.0, upper=1.0)


def calculate_vwma(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Calculate Volume Weighted Moving Average (VWMA).
    Weights closing price by volume over a rolling window.
    """
    if len(df) < period or df.empty:
        return pd.Series(index=df.index, dtype=float)

    pv = df['close'] * df['volume']
    vwma = pv.rolling(window=period).sum() / df['volume'].rolling(window=period).sum().replace(0, 1e-9)
    return vwma


def calculate_relative_volume(volume_series: pd.Series, period: int = 20) -> Tuple[pd.Series, float]:
    """
    Calculate Relative Volume (RVol) - ratio of current volume to 20-period moving average.
    Returns (rvol_series, latest_rvol). RVol > 2.0 indicates high volume spike.
    """
    if len(volume_series) < 2 or volume_series.empty:
        empty = pd.Series(1.0, index=volume_series.index)
        return empty, 1.0

    avg_vol = volume_series.rolling(window=period, min_periods=1).mean().replace(0, 1.0)
    rvol_series = (volume_series / avg_vol).round(2)
    latest_rvol = float(rvol_series.iloc[-1]) if not rvol_series.empty else 1.0

    return rvol_series, latest_rvol


def calculate_accumulation_distribution(df: pd.DataFrame) -> pd.Series:
    """
    Calculate Accumulation/Distribution Line (A/D).
    """
    if df.empty or 'high' not in df.columns or 'low' not in df.columns or 'close' not in df.columns:
        return pd.Series(dtype=float)

    high = df['high']
    low = df['low']
    close = df['close']
    volume = df['volume']

    clv = (((close - low) - (high - close)) / (high - low).replace(0, 1e-9))
    ad = (clv * volume).cumsum()
    return ad


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

    if timeframe_minutes < 60:
        rule = f"{timeframe_minutes}min"
    elif timeframe_minutes == 60:
        rule = "1h"
    elif timeframe_minutes == 240:
        rule = "4h"
    elif timeframe_minutes == 1440:
        rule = "1D"
    else:
        rule = f"{timeframe_minutes}min"

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


def calculate_pivot_points(daily_df: pd.DataFrame, fallback_price: float = 2428.50) -> Dict[str, float]:
    """
    Calculates Standard Classic Floor Pivot Points (PP, R1, R2, S1, S2)
    using the previous completed trading day's High, Low, Close.
    """
    if daily_df is not None and len(daily_df) >= 2:
        prev_day = daily_df.iloc[-2]
        h = float(prev_day['high'])
        l = float(prev_day['low'])
        c = float(prev_day['close'])
    elif daily_df is not None and len(daily_df) == 1:
        prev_day = daily_df.iloc[-1]
        h = float(prev_day['high'])
        l = float(prev_day['low'])
        c = float(prev_day['close'])
    else:
        h = fallback_price + 12.0
        l = fallback_price - 14.0
        c = fallback_price

    pp = round((h + l + c) / 3.0, 2)
    r1 = round(2.0 * pp - l, 2)
    s1 = round(2.0 * pp - h, 2)
    r2 = round(pp + (h - l), 2)
    s2 = round(pp - (h - l), 2)

    return {
        "pp": pp,
        "r1": r1,
        "r2": r2,
        "s1": s1,
        "s2": s2,
        "prev_high": round(h, 2),
        "prev_low": round(l, 2),
        "prev_close": round(c, 2)
    }


def calculate_order_flow_delta(candles_1m: List[Candle], lookback: int = 30) -> Dict[str, Any]:
    """
    Calculates intraday Buy vs Sell volume pressure and net delta from 1m candles over rolling window.
    """
    if not candles_1m:
        return {
            "buy_pct": 50,
            "sell_pct": 50,
            "delta_lots": 0,
            "delta_oz": 0.0,
            "status": "NEUTRAL",
            "formatted": "+0 oz (50% Buy)"
        }

    recent = candles_1m[-lookback:]
    buy_vol = 0.0
    sell_vol = 0.0

    for c in recent:
        if c.close >= c.open:
            buy_vol += c.volume
        else:
            sell_vol += c.volume

    total_vol = buy_vol + sell_vol
    if total_vol <= 0:
        return {
            "buy_pct": 50,
            "sell_pct": 50,
            "delta_lots": 0,
            "delta_oz": 0.0,
            "status": "NEUTRAL",
            "formatted": "+0 oz (50% Buy)"
        }

    buy_pct = int(round((buy_vol / total_vol) * 100))
    sell_pct = 100 - buy_pct
    delta_raw = buy_vol - sell_vol
    
    # Scale crypto PAXG volume units to standard retail ounces/contracts (normalized 1.0 - 50.0 range)
    delta_oz = round(delta_raw / 10.0, 1) if abs(delta_raw) > 500 else round(delta_raw, 1)
    delta_lots = int(round(delta_oz))

    status = "BUY_DOMINANT" if buy_pct >= 55 else ("SELL_DOMINANT" if sell_pct >= 55 else "BALANCED")
    formatted = f"{delta_oz:+.1f} oz ({buy_pct}% Buy)"

    return {
        "buy_pct": buy_pct,
        "sell_pct": sell_pct,
        "delta_lots": delta_lots,
        "delta_oz": delta_oz,
        "status": status,
        "formatted": formatted
    }
