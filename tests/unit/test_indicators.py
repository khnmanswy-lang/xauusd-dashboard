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
    resample_candles,
    calculate_bollinger_bands,
    calculate_macd,
    calculate_stochastic_rsi,
    calculate_obv,
    calculate_cmf,
    calculate_vwma,
    calculate_relative_volume,
    calculate_accumulation_distribution
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


def test_calculate_bollinger_bands():
    df = generate_synthetic_candles(60)
    mid, up, low, bw = calculate_bollinger_bands(df['close'], period=20, num_std=2.0)

    assert len(mid) == 60
    assert not mid.dropna().empty
    assert (up.dropna() >= mid.dropna()).all()
    assert (mid.dropna() >= low.dropna()).all()
    assert (bw.dropna() > 0).all()


def test_calculate_macd():
    df = generate_synthetic_candles(60)
    macd, signal, hist = calculate_macd(df['close'], fast=12, slow=26, signal=9)

    assert len(macd) == 60
    assert len(signal) == 60
    assert len(hist) == 60
    assert not macd.dropna().empty


def test_calculate_stochastic_rsi():
    df = generate_synthetic_candles(60)
    k, d = calculate_stochastic_rsi(df['close'], rsi_period=14, stoch_period=14, k_period=3, d_period=3)

    assert len(k) == 60
    assert len(d) == 60
    # Values bounded roughly between 0 and 100
    valid_k = k.dropna()
    assert (valid_k >= -1.0).all() and (valid_k <= 101.0).all()


def test_calculate_volume_indicators():
    df = generate_synthetic_candles(60)
    
    # OBV
    obv = calculate_obv(df)
    assert len(obv) == 60
    assert not obv.empty

    # CMF
    cmf = calculate_cmf(df, period=20)
    assert len(cmf) == 60
    assert (cmf.dropna() >= -1.0).all() and (cmf.dropna() <= 1.0).all()

    # VWMA
    vwma = calculate_vwma(df, period=20)
    assert len(vwma) == 60
    assert not vwma.dropna().empty

    # Relative Volume (RVol)
    rvol_series, latest_rvol = calculate_relative_volume(df['volume'], period=20)
    assert len(rvol_series) == 60
    assert latest_rvol > 0

    # Accumulation / Distribution
    ad = calculate_accumulation_distribution(df)
    assert len(ad) == 60
    assert not ad.empty


def test_calculate_pivot_points():
    from src.core.indicators import calculate_pivot_points
    daily_df = pd.DataFrame([
        {"timestamp": 1700000000, "open": 2400.0, "high": 2420.0, "low": 2390.0, "close": 2410.0, "volume": 1000},
        {"timestamp": 1700086400, "open": 2410.0, "high": 2435.0, "low": 2413.0, "close": 2428.0, "volume": 1500},
    ])
    pivots = calculate_pivot_points(daily_df, 2428.0)
    assert "pp" in pivots
    assert "r1" in pivots
    assert "r2" in pivots
    assert "s1" in pivots
    assert "s2" in pivots
    assert pivots["r2"] > pivots["r1"] > pivots["pp"] > pivots["s1"] > pivots["s2"]


def test_calculate_order_flow_delta():
    from src.core.indicators import calculate_order_flow_delta, Candle
    candles = [
        Candle(timestamp=100, open=2400.0, high=2402.0, low=2399.0, close=2401.0, volume=100.0), # Buy
        Candle(timestamp=160, open=2401.0, high=2403.0, low=2400.0, close=2402.5, volume=150.0), # Buy
        Candle(timestamp=220, open=2402.5, high=2403.0, low=2398.0, close=2399.0, volume=50.0),  # Sell
    ]
    of = calculate_order_flow_delta(candles)
    assert of["buy_pct"] > of["sell_pct"]
    assert of["delta_lots"] == 200
    assert of["status"] == "BUY_DOMINANT"


