"""
Unit tests for Structure & Liquidity Engine (src/core/structure.py).
"""
import pytest
import pandas as pd
from datetime import datetime, timezone

from src.core.structure import (
    FairValueGap,
    OrderBlock,
    SessionLevels,
    get_current_session_info,
    calculate_session_levels,
    detect_liquidity_sweeps,
    detect_fair_value_gaps,
    detect_order_blocks,
    detect_break_of_structure,
    calculate_confluence_matrix
)


def test_get_current_session_info():
    # 02:30 UTC -> Asia Open
    dt_asia = datetime(2026, 8, 22, 2, 30, tzinfo=timezone.utc)
    sess, kz = get_current_session_info(dt_asia)
    assert sess == "ASIA"
    assert kz == "ASIA_OPEN"

    # 08:30 UTC -> London
    dt_london = datetime(2026, 8, 22, 8, 30, tzinfo=timezone.utc)
    sess, kz = get_current_session_info(dt_london)
    assert sess == "LONDON"
    assert kz == "LONDON_OPEN"

    # 14:00 UTC -> New York
    dt_ny = datetime(2026, 8, 22, 14, 0, tzinfo=timezone.utc)
    sess, kz = get_current_session_info(dt_ny)
    assert sess == "NEW_YORK"
    assert kz == "NY_OPEN"


def test_calculate_session_levels():
    # Simulate candles during Asia session (02:00 to 06:00 UTC)
    base_date = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)
    base_ts = int(base_date.timestamp())

    m5_candles = []
    for i in range(50):
        ts = base_ts + (i * 300)  # 5min steps
        m5_candles.append({
            'timestamp': ts,
            'open': 2930.0,
            'high': 2940.0 if i == 10 else 2935.0,
            'low': 2920.0 if i == 20 else 2925.0,
            'close': 2930.0,
            'volume': 100.0
        })
    df_m5 = pd.DataFrame(m5_candles)

    daily_df = pd.DataFrame({
        'high': [2950.0, 2960.0],
        'low': [2910.0, 2915.0],
        'close': [2940.0, 2930.0]
    })

    eval_time = datetime(2026, 8, 22, 9, 0, tzinfo=timezone.utc)
    levels = calculate_session_levels(df_m5, daily_df, eval_time)

    assert levels.asia_high == 2940.0
    assert levels.asia_low == 2920.0
    assert levels.pdh == 2950.0
    assert levels.pdl == 2910.0


def test_detect_liquidity_sweeps():
    levels = SessionLevels(asia_high=2940.0, asia_low=2920.0)

    # Bullish Asia Low Sweep candle (pierced 2918, closed at 2922)
    sweep_df = pd.DataFrame({
        'high': [2930.0, 2925.0],
        'low': [2925.0, 2918.0],
        'close': [2926.0, 2922.0]
    })
    sweep = detect_liquidity_sweeps(sweep_df, levels)
    assert sweep == "ASIA_LOW_SWEPT"

    # Bearish Asia High Sweep candle (pierced 2943, closed at 2938)
    high_sweep_df = pd.DataFrame({
        'high': [2935.0, 2943.0],
        'low': [2930.0, 2935.0],
        'close': [2932.0, 2938.0]
    })
    sweep_high = detect_liquidity_sweeps(high_sweep_df, levels)
    assert sweep_high == "ASIA_HIGH_SWEPT"


def test_detect_fair_value_gaps():
    # 3-candle sequence creating a Bullish FVG
    # c0: high=2930.0
    # c1: impulsive up bar
    # c2: low=2934.0 -> Gap is [2930.0, 2934.0]
    df = pd.DataFrame({
        'timestamp': [1740000000, 1740000300, 1740000600],
        'open': [2925.0, 2930.0, 2936.0],
        'high': [2930.0, 2938.0, 2942.0],
        'low': [2924.0, 2929.0, 2934.0],
        'close': [2929.0, 2937.0, 2940.0],
        'volume': [100.0, 300.0, 200.0]
    })

    fvgs = detect_fair_value_gaps(df)
    assert len(fvgs) == 1
    assert fvgs[0].type == "BULLISH"
    assert fvgs[0].bottom == 2930.0
    assert fvgs[0].top == 2934.0
    assert not fvgs[0].mitigated


def test_calculate_confluence_matrix():
    fvg = FairValueGap(type="BULLISH", top=2935.0, bottom=2930.0, timestamp=1740000000, mitigated=False)
    matrix = calculate_confluence_matrix(
        current_price=2940.0,
        h1_ema200=2920.0,  # +1
        h1_rsi=58.0,
        m15_vwap=2935.0,   # +1
        m15_rsi_div="REGULAR_BULLISH",  # +1
        m5_sweep="ASIA_LOW_SWEPT",       # +1
        active_fvgs=[fvg]                # +1 (above unmitigated bullish fvg)
    )

    assert matrix['h1']['bias'] == "BULLISH"
    assert matrix['score_value'] > 0
    assert "BULLISH" in matrix['overall_score']


def test_detect_order_blocks():
    # Sequence with a down candle followed by 2 strong up candles breaking highs
    candles = [
        {'timestamp': 1740000000, 'open': 2930.0, 'high': 2932.0, 'low': 2928.0, 'close': 2931.0, 'volume': 100},
        {'timestamp': 1740000300, 'open': 2931.0, 'high': 2932.0, 'low': 2927.0, 'close': 2928.0, 'volume': 150},  # Bearish OB
        {'timestamp': 1740000600, 'open': 2928.0, 'high': 2938.0, 'low': 2928.0, 'close': 2936.0, 'volume': 400},  # Impulse up
        {'timestamp': 1740000900, 'open': 2936.0, 'high': 2945.0, 'low': 2935.0, 'close': 2944.0, 'volume': 500},  # Impulse continuation
        {'timestamp': 1740001200, 'open': 2944.0, 'high': 2946.0, 'low': 2942.0, 'close': 2945.0, 'volume': 200},
    ]
    df = pd.DataFrame(candles)
    blocks = detect_order_blocks(df, current_price=2945.0)

    assert len(blocks) >= 1
    assert blocks[0].type == "BULLISH"
    assert blocks[0].bottom == 2927.0
    assert blocks[0].top == 2932.0


def test_detect_break_of_structure():
    # 25 candles with prior range 2920 - 2940, and latest candle breaking above 2940
    data = []
    for i in range(24):
        data.append({
            'timestamp': 1740000000 + i * 300,
            'open': 2930.0,
            'high': 2940.0 if i == 5 else 2935.0,
            'low': 2920.0 if i == 10 else 2925.0,
            'close': 2930.0,
            'volume': 100
        })
    # Breakout candle
    data.append({
        'timestamp': 1740000000 + 24 * 300,
        'open': 2938.0,
        'high': 2948.0,
        'low': 2937.0,
        'close': 2946.0,
        'volume': 600
    })
    df = pd.DataFrame(data)
    bos = detect_break_of_structure(df)

    assert bos is not None
    assert bos['type'] == "BULLISH_BOS"
    assert bos['level'] == 2940.0

