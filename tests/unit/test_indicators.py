"""
Unit tests for Core Quantitative Analytics Engine (src/core/indicators.py).
"""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from src.core.indicators import (
    Candle,
    calculate_ema,
    calculate_atr,
    calculate_adr,
    calculate_session_vwap,
    calculate_rsi,
    detect_rsi_divergence,
    resample_candles
)


def generate_synthetic_candles(n: int = 100, base_price: float = 2900.0, trend: float = 0.5) -> pd.DataFrame:
    """Helper to generate deterministic synthetic OHLCV data."""
    start_ts = 1740000000 - (1740000000 % 3600)  # Align to top of hour
    timestamps = [start_ts + (i * 60) for i in range(n)]
    
    closes = [base_price + (i * trend) + (np.sin(i / 5.0) * 5.0) for i in range(n)]
    highs = [c + 2.0 for c in closes]
    lows = [c - 2.0 for c in closes]
    opens = [closes[max(0, i - 1)] for i in range(n)]
    volumes = [100.0 + (i % 10) * 10 for i in range(n)]

    return pd.DataFrame({
        'timestamp': timestamps,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    })


def test_candle_dataclass():
    c = Candle(timestamp=1740000000, open=2900.123, high=2905.456, low=2895.789, close=2902.999, volume=150.0)
    d = c.to_dict()
    assert d['time'] == 1740000000
    assert d['open'] == 2900.12
    assert d['high'] == 2905.46
    assert d['low'] == 2895.79
    assert d['close'] == 2903.0


def test_calculate_ema():
    df = generate_synthetic_candles(50)
    ema20 = calculate_ema(df['close'], 20)
    assert len(ema20) == 50
    assert not ema20.isna().all()
    # In an uptrend, EMA should lag slightly behind current close
    assert ema20.iloc[-1] > df['close'].iloc[0]


def test_calculate_atr():
    df = generate_synthetic_candles(50)
    atr = calculate_atr(df, period=14)
    assert len(atr) == 50
    # True range should be around 4.0 (high - low is 4.0)
    assert 3.5 <= atr.iloc[-1] <= 6.0


def test_calculate_adr():
    # 5 days of synthetic daily candles
    daily_df = pd.DataFrame({
        'high': [2920.0, 2930.0, 2945.0, 2940.0, 2935.0],
        'low': [2890.0, 2900.0, 2910.0, 2915.0, 2920.0],
        'close': [2910.0, 2925.0, 2930.0, 2930.0, 2930.0]
    })
    adr_total, current_range, adr_pct = calculate_adr(daily_df, period=4)
    assert adr_total > 0
    assert current_range == 15.0  # 2935 - 2920
    assert 0 < adr_pct < 100


def test_calculate_session_vwap():
    df = generate_synthetic_candles(60)
    vwap, u1, u2, l1, l2 = calculate_session_vwap(df)
    
    assert len(vwap) == len(df)
    assert len(u1) == len(df)
    assert len(u2) == len(df)
    
    # Check band ordering: u2 > u1 >= vwap >= l1 > l2
    last_idx = -1
    assert u2.iloc[last_idx] >= u1.iloc[last_idx]
    assert u1.iloc[last_idx] >= vwap.iloc[last_idx]
    assert vwap.iloc[last_idx] >= l1.iloc[last_idx]
    assert l1.iloc[last_idx] >= l2.iloc[last_idx]


def test_calculate_rsi():
    # Uptrending series should produce high RSI
    up_series = pd.Series([100.0 + (i * 2.0) for i in range(30)])
    rsi = calculate_rsi(up_series, period=14)
    assert rsi.iloc[-1] > 70.0

    # Downtrending series should produce low RSI
    down_series = pd.Series([200.0 - (i * 2.0) for i in range(30)])
    rsi_down = calculate_rsi(down_series, period=14)
    assert rsi_down.iloc[-1] < 30.0


def test_resample_candles():
    df_1m = generate_synthetic_candles(60)
    df_5m = resample_candles(df_1m, 5)
    df_15m = resample_candles(df_1m, 15)

    assert len(df_5m) == 12
    assert len(df_15m) == 4
    assert 'open' in df_5m.columns and 'close' in df_5m.columns
