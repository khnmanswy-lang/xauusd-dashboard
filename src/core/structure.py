"""
Structure & Liquidity Engine for XAUUSD Multi-Timeframe Analysis.
Handles Asian Range, PDH/PDL, Liquidity Sweeps, FVGs, and MTF Confluence Matrix.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np


@dataclass
class FairValueGap:
    """Represents a Fair Value Gap (FVG) imbalance."""
    type: str  # 'BULLISH' or 'BEARISH'
    top: float
    bottom: float
    timestamp: int
    mitigated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "top": round(self.top, 2),
            "bottom": round(self.bottom, 2),
            "timestamp": self.timestamp,
            "mitigated": self.mitigated
        }


@dataclass
class SessionLevels:
    """Tracks session benchmarks and key liquidity reference levels."""
    active_session: str = "LONDON"
    killzone: Optional[str] = None
    asia_high: Optional[float] = None
    asia_low: Optional[float] = None
    pdh: Optional[float] = None
    pdl: Optional[float] = None
    recent_sweep: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_session": self.active_session,
            "killzone": self.killzone or "NONE",
            "asia_high": round(self.asia_high, 2) if self.asia_high is not None else None,
            "asia_low": round(self.asia_low, 2) if self.asia_low is not None else None,
            "pdh": round(self.pdh, 2) if self.pdh is not None else None,
            "pdl": round(self.pdl, 2) if self.pdl is not None else None,
            "recent_sweep": self.recent_sweep
        }


def get_current_session_info(current_time: Optional[datetime] = None) -> Tuple[str, Optional[str]]:
    """
    Determine active trading session and killzone based on current UTC time.
    """
    now = current_time or datetime.now(timezone.utc)
    hour = now.hour
    minute = now.minute
    time_float = hour + minute / 60.0

    session = "CLOSED"
    killzone = None

    # Asian session: 00:00 - 08:00 UTC
    if 0 <= time_float < 8:
        session = "ASIA"
        if 0 <= time_float < 3:
            killzone = "ASIA_OPEN"

    # London session: 07:00 - 16:00 UTC
    if 7 <= time_float < 16:
        session = "LONDON"
        if 7 <= time_float < 10:
            killzone = "LONDON_OPEN"

    # NY session: 12:00 - 21:00 UTC (Overlaps London between 12:00 - 16:00)
    if 12 <= time_float < 21:
        session = "NEW_YORK"
        if 12 <= time_float < 15:
            killzone = "NY_OPEN"
        elif 19 <= time_float < 21:
            killzone = "NY_CLOSE"

    return session, killzone


def calculate_session_levels(
    m5_df: pd.DataFrame,
    daily_df: Optional[pd.DataFrame] = None,
    current_time: Optional[datetime] = None
) -> SessionLevels:
    """
    Calculate Asia High/Low, Previous Day High (PDH), and Previous Day Low (PDL).
    """
    levels = SessionLevels()
    now = current_time or datetime.now(timezone.utc)
    levels.active_session, levels.killzone = get_current_session_info(now)

    # Previous Day High / Low from daily candles
    if daily_df is not None and len(daily_df) >= 2:
        prev_day = daily_df.iloc[-2]
        levels.pdh = float(prev_day['high'])
        levels.pdl = float(prev_day['low'])

    if m5_df.empty:
        return levels

    df = m5_df.copy()
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)

    today_date = now.date()
    today_candles = df[df['dt'].dt.date == today_date]

    # Asia session candles: 00:00 to 08:00 UTC today
    asia_candles = today_candles[(today_candles['dt'].dt.hour >= 0) & (today_candles['dt'].dt.hour < 8)]

    if not asia_candles.empty:
        levels.asia_high = float(asia_candles['high'].max())
        levels.asia_low = float(asia_candles['low'].min())

    return levels


def detect_liquidity_sweeps(
    m5_df: pd.DataFrame,
    levels: SessionLevels,
    lookback: int = 6
) -> Optional[str]:
    """
    Detect liquidity sweeps:
    - High pierced above Asia High or PDH, but candle closed back below (or rejected).
    - Low pierced below Asia Low or PDL, but candle closed back above (or rejected).
    """
    if m5_df.empty or len(m5_df) < 2:
        return None

    recent = m5_df.tail(lookback)

    # Check Asia Low Sweep
    if levels.asia_low is not None:
        for _, candle in recent.iterrows():
            if candle['low'] < levels.asia_low and candle['close'] > levels.asia_low:
                return "ASIA_LOW_SWEPT"

    # Check Asia High Sweep
    if levels.asia_high is not None:
        for _, candle in recent.iterrows():
            if candle['high'] > levels.asia_high and candle['close'] < levels.asia_high:
                return "ASIA_HIGH_SWEPT"

    # Check PDL Sweep
    if levels.pdl is not None:
        for _, candle in recent.iterrows():
            if candle['low'] < levels.pdl and candle['close'] > levels.pdl:
                return "PDL_SWEPT"

    # Check PDH Sweep
    if levels.pdh is not None:
        for _, candle in recent.iterrows():
            if candle['high'] > levels.pdh and candle['close'] < levels.pdh:
                return "PDH_SWEPT"

    return None


def detect_fair_value_gaps(m5_df: pd.DataFrame, max_gaps: int = 5) -> List[FairValueGap]:
    """
    Detect recent 3-candle Fair Value Gaps (FVG) and determine whether they are mitigated.
    Bullish FVG: candle[i].low > candle[i-2].high (imbalance gap between candle 0 high and candle 2 low)
    Bearish FVG: candle[i].high < candle[i-2].low (imbalance gap between candle 0 low and candle 2 high)
    """
    if len(m5_df) < 3:
        return []

    gaps: List[FairValueGap] = []
    current_price = float(m5_df['close'].iloc[-1])

    # Scan starting from 3rd candle up to current
    for i in range(2, len(m5_df)):
        c0 = m5_df.iloc[i - 2]
        c1 = m5_df.iloc[i - 1]
        c2 = m5_df.iloc[i]

        # Bullish FVG
        if c2['low'] > c0['high']:
            gap_top = float(c2['low'])
            gap_bottom = float(c0['high'])
            
            # Check if mitigated by any subsequent candles
            subsequent = m5_df.iloc[i + 1:]
            mitigated = False
            if not subsequent.empty:
                if (subsequent['low'] <= gap_bottom).any():
                    mitigated = True
            elif current_price <= gap_bottom:
                mitigated = True

            gaps.append(FairValueGap(
                type="BULLISH",
                top=gap_top,
                bottom=gap_bottom,
                timestamp=int(c1['timestamp']),
                mitigated=mitigated
            ))

        # Bearish FVG
        elif c2['high'] < c0['low']:
            gap_top = float(c0['low'])
            gap_bottom = float(c2['high'])

            # Check if mitigated by any subsequent candles
            subsequent = m5_df.iloc[i + 1:]
            mitigated = False
            if not subsequent.empty:
                if (subsequent['high'] >= gap_top).any():
                    mitigated = True
            elif current_price >= gap_top:
                mitigated = True

            gaps.append(FairValueGap(
                type="BEARISH",
                top=gap_top,
                bottom=gap_bottom,
                timestamp=int(c1['timestamp']),
                mitigated=mitigated
            ))

    # Return the most recent unmitigated or latest gaps
    return gaps[-max_gaps:] if gaps else []


def calculate_confluence_matrix(
    current_price: float,
    h1_ema200: Optional[float],
    h1_rsi: Optional[float],
    m15_vwap: Optional[float],
    m15_rsi_div: Optional[str],
    m5_sweep: Optional[str],
    active_fvgs: List[FairValueGap]
) -> Dict[str, Any]:
    """
    Score multi-timeframe confluence:
    - H1: Long-term trend bias (Above/Below 200 EMA + RSI cycle)
    - M15: Intraday structure bias (Above/Below Session VWAP + RSI Divergence)
    - M5: Execution trigger (Asia/PDH/PDL Sweeps + Active FVG)
    """
    score = 0

    # 1. H1 Analysis
    h1_bias = "NEUTRAL"
    if h1_ema200 is not None:
        if current_price > h1_ema200:
            h1_bias = "BULLISH"
            score += 1
        else:
            h1_bias = "BEARISH"
            score -= 1

    # 2. M15 Analysis
    m15_structure = "NEUTRAL"
    if m15_vwap is not None:
        if current_price > m15_vwap:
            m15_structure = "BULLISH_VWAP"
            score += 1
        else:
            m15_structure = "BEARISH_VWAP"
            score -= 1

    if m15_rsi_div == "REGULAR_BULLISH" or m15_rsi_div == "HIDDEN_BULLISH":
        score += 1
        m15_structure += " + RSI_BULL_DIV"
    elif m15_rsi_div == "REGULAR_BEARISH" or m15_rsi_div == "HIDDEN_BEARISH":
        score -= 1
        m15_structure += " + RSI_BEAR_DIV"

    # 3. M5 Triggers
    m5_signal = "WAITING"
    if m5_sweep in ["ASIA_LOW_SWEPT", "PDL_SWEPT"]:
        score += 1
        m5_signal = "BUY_TRIGGER (SWEEP)"
    elif m5_sweep in ["ASIA_HIGH_SWEPT", "PDH_SWEPT"]:
        score -= 1
        m5_signal = "SELL_TRIGGER (SWEEP)"

    # Check unmitigated FVGs near price
    fvg_zone = None
    for g in reversed(active_fvgs):
        if not g.mitigated:
            fvg_zone = [g.bottom, g.top]
            if g.type == "BULLISH" and current_price >= g.bottom:
                score += 1
            elif g.type == "BEARISH" and current_price <= g.top:
                score -= 1
            break

    # Format Overall Score
    if score > 0:
        overall = f"+{score} BULLISH"
    elif score < 0:
        overall = f"{score} BEARISH"
    else:
        overall = "0 NEUTRAL"

    return {
        "h1": {
            "bias": h1_bias,
            "ema_200": round(h1_ema200, 2) if h1_ema200 else None,
            "rsi": round(h1_rsi, 1) if h1_rsi else None
        },
        "m15": {
            "structure": m15_structure,
            "vwap": round(m15_vwap, 2) if m15_vwap else None,
            "rsi_div": m15_rsi_div
        },
        "m5": {
            "signal": m5_signal,
            "sweep": m5_sweep or "NONE",
            "fvg": fvg_zone
        },
        "score_value": score,
        "overall_score": overall
    }
