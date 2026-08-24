"""
Unit tests for Institutional Setup Scanner Engine (src/core/setup_scanner.py).
"""
import pytest
import pandas as pd
from datetime import datetime, timezone

from src.core.structure import SessionLevels, FairValueGap
from src.core.setup_scanner import (
    SetupResult,
    detect_m5_choch,
    check_fvg_retest,
    scan_market_setup
)
from src.integrations.market_data import MarketDataEngine


def generate_m5_test_data(pattern: str = "bullish_choch") -> pd.DataFrame:
    """Helper to generate deterministic M5 price action sequences."""
    base_ts = 1740000000
    rows = []

    if pattern == "bullish_choch":
        # 1. Pullback candle (high: 2933.0, close: 2928.0)
        # 2. Sweep lowest low down to 2920.0 (high: 2928.0)
        # 3. Impulsive displacement closing at 2936.0 (> 2933.0 swing high)
        # 4. Retrace candle to 2933.0
        prices = [
            (2930.0, 2933.0, 2926.0, 2928.0),  # c0 (prior swing high: 2933.0)
            (2928.0, 2929.0, 2920.0, 2922.0),  # c1: lowest low (2920.0)
            (2922.0, 2928.0, 2921.0, 2927.0),  # c2
            (2927.0, 2938.0, 2926.0, 2936.0),  # c3: breaks & closes above 2933.0 swing high
            (2936.0, 2937.0, 2931.0, 2933.0)   # c4: current bar (retesting 2933)
        ]
        for i, (o, h, l, c) in enumerate(prices):
            rows.append({
                'timestamp': base_ts + (i * 300),
                'open': o, 'high': h, 'low': l, 'close': c, 'volume': 100.0
            })

    elif pattern == "bearish_choch":
        # 1. Rally candle (low: 2938.0, high: 2946.0)
        # 2. Sweep highest high up to 2955.0 (low: 2944.0)
        # 3. Impulsive displacement closing at 2932.0 (< 2938.0 swing low)
        # 4. Retrace candle to 2939.0
        prices = [
            (2940.0, 2946.0, 2938.0, 2944.0),  # c0 (prior swing low: 2938.0)
            (2944.0, 2955.0, 2942.0, 2952.0),  # c1: highest high (2955.0)
            (2952.0, 2953.0, 2940.0, 2942.0),  # c2
            (2942.0, 2943.0, 2930.0, 2932.0),  # c3: breaks & closes below 2938.0 swing low
            (2932.0, 2940.0, 2931.0, 2939.0)   # c4: current bar (retesting 2939)
        ]
        for i, (o, h, l, c) in enumerate(prices):
            rows.append({
                'timestamp': base_ts + (i * 300),
                'open': o, 'high': h, 'low': l, 'close': c, 'volume': 100.0
            })

    return pd.DataFrame(rows)


def test_detect_m5_choch_bullish():
    df = generate_m5_test_data("bullish_choch")
    choch_ok, level = detect_m5_choch(df, direction="BULLISH")
    assert choch_ok is True
    assert level is not None
    assert level >= 2930.0


def test_detect_m5_choch_bearish():
    df = generate_m5_test_data("bearish_choch")
    choch_ok, level = detect_m5_choch(df, direction="BEARISH")
    assert choch_ok is True
    assert level is not None
    assert level <= 2940.0


def test_check_fvg_retest():
    fvg_bullish = FairValueGap(type="BULLISH", top=2935.0, bottom=2930.0, timestamp=1740000000, mitigated=False)
    
    # 1. Price is inside the FVG (2932.50 = CE)
    hit, matched, ce = check_fvg_retest([fvg_bullish], current_price=2932.50, direction="BULLISH")
    assert hit is True
    assert matched == fvg_bullish
    assert ce == 2932.50

    # 2. Price far away from FVG
    hit_far, _, _ = check_fvg_retest([fvg_bullish], current_price=2960.00, direction="BULLISH")
    assert hit_far is False

    # 3. Mitigated FVG should not trigger
    fvg_mitigated = FairValueGap(type="BULLISH", top=2935.0, bottom=2930.0, timestamp=1740000000, mitigated=True)
    hit_mitigated, _, _ = check_fvg_retest([fvg_mitigated], current_price=2932.50, direction="BULLISH")
    assert hit_mitigated is False


def test_scan_market_setup_grade_a_bullish():
    m5_df = generate_m5_test_data("bullish_choch")
    levels = SessionLevels(asia_high=2945.0, asia_low=2925.0, recent_sweep="ASIA_LOW_SWEPT")
    fvg = FairValueGap(type="BULLISH", top=2935.0, bottom=2931.0, timestamp=1740000300, mitigated=False)

    result = scan_market_setup(
        current_price=2933.0,
        m5_df=m5_df,
        levels=levels,
        fvgs=[fvg],
        m15_vwap=2930.0,
        h1_ema200=2920.0,
        adr_used_pct=45.0,
        news_guard_active=False,
        atr_m5=2.0
    )

    assert result.grade == "GRADE_A"
    assert result.direction == "BULLISH_LONG"
    assert result.confidence_score >= 0.85
    assert result.points_checked["sweep"] is True
    assert result.points_checked["choch"] is True
    assert result.points_checked["fvg_retest"] is True
    assert result.points_checked["macro_alignment"] is True
    assert result.points_checked["adr_news_clear"] is True
    assert result.points_met == 5
    assert result.suggested_entry == 2933.0
    assert result.suggested_sl < result.suggested_entry
    assert result.suggested_tp1 > result.suggested_entry
    assert result.suggested_tp2 == 2945.0  # Asian High target


def test_scan_market_setup_grade_a_bearish():
    m5_df = generate_m5_test_data("bearish_choch")
    levels = SessionLevels(asia_high=2950.0, asia_low=2928.0, recent_sweep="ASIA_HIGH_SWEPT")
    fvg = FairValueGap(type="BEARISH", top=2942.0, bottom=2936.0, timestamp=1740000300, mitigated=False)

    result = scan_market_setup(
        current_price=2939.0,
        m5_df=m5_df,
        levels=levels,
        fvgs=[fvg],
        m15_vwap=2944.0,
        h1_ema200=2955.0,
        adr_used_pct=50.0,
        news_guard_active=False,
        atr_m5=2.0
    )

    assert result.grade == "GRADE_A"
    assert result.direction == "BEARISH_SHORT"
    assert result.confidence_score >= 0.85
    assert result.points_checked["sweep"] is True
    assert result.points_checked["choch"] is True
    assert result.points_checked["fvg_retest"] is True
    assert result.suggested_entry == 2939.0
    assert result.suggested_sl > result.suggested_entry
    assert result.suggested_tp1 < result.suggested_entry
    assert result.suggested_tp2 == 2928.0  # Asian Low target


def test_scan_market_setup_no_setup_consolidation():
    levels = SessionLevels(asia_high=2940.0, asia_low=2930.0, recent_sweep=None)
    result = scan_market_setup(
        current_price=2935.0,
        m5_df=pd.DataFrame(),
        levels=levels,
        fvgs=[],
        m15_vwap=None,
        h1_ema200=None,
        adr_used_pct=90.0,
        news_guard_active=True
    )

    assert result.grade == "NO_SETUP"
    assert result.direction == "NEUTRAL"
    assert result.confidence_score <= 0.50


def test_market_data_engine_state_includes_setup_scan():
    engine = MarketDataEngine()
    engine.process_tick(2935.0)
    frame = engine.get_state_frame()

    assert "setup_scan" in frame
    scan = frame["setup_scan"]
    assert "grade" in scan
    assert "direction" in scan
    assert "confidence_score" in scan
    assert "points_checked" in scan
    assert "suggested_entry" in scan
    assert "suggested_sl" in scan
    assert "suggested_tp1" in scan
    assert "suggested_tp2" in scan
