"""
Institutional Setup Scanner Engine for XAUUSD Multi-Timeframe Dashboard.
Detects 5-point confluence setups:
1. Session Liquidity Sweep (Asian Range High/Low or PDH/PDL)
2. Micro Structure Shift (M5 CHoCH - Change of Character)
3. Fair Value Gap (FVG) Retest at Consequent Encroachment (50% CE)
4. Macro Alignment (H1 200 EMA + Session VWAP)
5. Exhaustion Guard (ADR used < 80% and News Clear > 15m)
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from src.core.indicators import Candle
from src.core.structure import SessionLevels, FairValueGap


@dataclass
class SetupResult:
    """Represents a scanned trade setup and execution parameters."""
    grade: str  # 'GRADE_A', 'GRADE_B', 'NO_SETUP'
    direction: str  # 'BULLISH_LONG', 'BEARISH_SHORT', 'NEUTRAL'
    confidence_score: float  # 0.0 to 1.0
    setup_type: str
    points_checked: Dict[str, bool] = field(default_factory=dict)
    points_met: int = 0
    suggested_entry: Optional[float] = None
    suggested_sl: Optional[float] = None
    suggested_tp1: Optional[float] = None
    suggested_tp2: Optional[float] = None
    risk_reward_ratio: float = 2.0
    invalidation_trigger: str = ""
    reasons: List[str] = field(default_factory=list)
    timestamp: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "grade": self.grade,
            "direction": self.direction,
            "confidence_score": round(self.confidence_score, 2),
            "setup_type": self.setup_type,
            "points_checked": self.points_checked,
            "points_met": self.points_met,
            "suggested_entry": round(self.suggested_entry, 2) if self.suggested_entry is not None else None,
            "suggested_sl": round(self.suggested_sl, 2) if self.suggested_sl is not None else None,
            "suggested_tp1": round(self.suggested_tp1, 2) if self.suggested_tp1 is not None else None,
            "suggested_tp2": round(self.suggested_tp2, 2) if self.suggested_tp2 is not None else None,
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "invalidation_trigger": self.invalidation_trigger,
            "reasons": self.reasons,
            "timestamp": self.timestamp
        }


def detect_m5_choch(
    m5_df: pd.DataFrame,
    direction: str = "BULLISH",
    lookback: int = 12
) -> Tuple[bool, Optional[float]]:
    """
    Detect M5 Micro Structure Shift / Change of Character (CHoCH).
    - BULLISH: Identifies recent swing high before the lowest low, and checks if subsequent candle broke & closed above it.
    - BEARISH: Identifies recent swing low before highest high, and checks if subsequent candle broke & closed below it.
    """
    if m5_df.empty or len(m5_df) < 5:
        return False, None

    df = m5_df.tail(lookback).reset_index(drop=True)
    n = len(df)
    if n < 4:
        return False, None

    if direction == "BULLISH":
        # Find index of lowest low (sweep point)
        min_idx = int(df['low'].iloc[:-1].idxmin())
        if min_idx == 0:
            swing_high = float(df['high'].iloc[:min_idx + 2].max())
        else:
            # Look at immediate prior swing high before lowest low
            start_idx = max(0, min_idx - 3)
            swing_high = float(df['high'].iloc[start_idx:min_idx].max())

        # Check if any candle after min_idx closed above swing_high
        for i in range(min_idx + 1, n):
            if df['close'].iloc[i] > swing_high:
                return True, round(swing_high, 2)

    elif direction == "BEARISH":
        # Find index of highest high (sweep point)
        max_idx = int(df['high'].iloc[:-1].idxmax())
        if max_idx == 0:
            swing_low = float(df['low'].iloc[:max_idx + 2].min())
        else:
            # Look at immediate prior swing low before highest high
            start_idx = max(0, max_idx - 3)
            swing_low = float(df['low'].iloc[start_idx:max_idx].min())

        # Check if any candle after max_idx closed below swing_low
        for i in range(max_idx + 1, n):
            if df['close'].iloc[i] < swing_low:
                return True, round(swing_low, 2)

    return False, None


def check_fvg_retest(
    fvgs: List[FairValueGap],
    current_price: float,
    direction: str = "BULLISH",
    tolerance_usd: float = 1.50
) -> Tuple[bool, Optional[FairValueGap], Optional[float]]:
    """
    Check if price is actively retesting an unmitigated FVG or its 50% Consequent Encroachment (CE).
    """
    if not fvgs:
        return False, None, None

    target_type = "BULLISH" if direction == "BULLISH" else "BEARISH"
    for fvg in reversed(fvgs):
        if fvg.type == target_type and not fvg.mitigated:
            ce_level = round((fvg.top + fvg.bottom) / 2.0, 2)
            # Check if current price is within [bottom - tol, top + tol]
            if (fvg.bottom - tolerance_usd) <= current_price <= (fvg.top + tolerance_usd):
                return True, fvg, ce_level

    return False, None, None


def scan_market_setup(
    current_price: float,
    m5_df: pd.DataFrame,
    levels: SessionLevels,
    fvgs: List[FairValueGap],
    m15_vwap: Optional[float],
    h1_ema200: Optional[float],
    adr_used_pct: float,
    news_guard_active: bool,
    atr_m5: float = 2.0,
    timestamp: Optional[int] = None
) -> SetupResult:
    """
    Evaluates market conditions against the 5-point Institutional Confluence model.
    """
    now_ts = timestamp or int(datetime.now(timezone.utc).timestamp())
    sweep = levels.recent_sweep

    # Determine potential setup direction based on sweep or trend
    bullish_sweep = sweep in ["ASIA_LOW_SWEPT", "PDL_SWEPT"]
    bearish_sweep = sweep in ["ASIA_HIGH_SWEPT", "PDH_SWEPT"]

    direction = "NEUTRAL"
    if bullish_sweep:
        direction = "BULLISH_LONG"
    elif bearish_sweep:
        direction = "BEARISH_SHORT"
    elif m15_vwap is not None and h1_ema200 is not None:
        if current_price > m15_vwap and current_price > h1_ema200:
            direction = "BULLISH_LONG"
        elif current_price < m15_vwap and current_price < h1_ema200:
            direction = "BEARISH_SHORT"

    if direction == "NEUTRAL":
        return SetupResult(
            grade="NO_SETUP",
            direction="NEUTRAL",
            confidence_score=0.20,
            setup_type="Market Consolidating / Neutral Regime",
            points_checked={
                "sweep": False,
                "choch": False,
                "fvg_retest": False,
                "macro_alignment": False,
                "adr_news_clear": False
            },
            points_met=0,
            invalidation_trigger="Awaiting Asian Range breakout or liquidity sweep trigger.",
            reasons=["No structural liquidity sweep detected.", "Price consolidating within session boundaries."],
            timestamp=now_ts
        )

    # 1. Sweep Point
    sweep_ok = bullish_sweep if direction == "BULLISH_LONG" else bearish_sweep

    # 2. CHoCH Point
    choch_dir = "BULLISH" if direction == "BULLISH_LONG" else "BEARISH"
    choch_ok, choch_level = detect_m5_choch(m5_df, direction=choch_dir)

    # 3. FVG Retest Point
    fvg_ok, matched_fvg, ce_level = check_fvg_retest(fvgs, current_price, direction=choch_dir)

    # 4. Macro Confluence Point
    macro_ok = False
    if direction == "BULLISH_LONG":
        vwap_aligned = (m15_vwap is not None and current_price >= m15_vwap)
        ema_aligned = (h1_ema200 is not None and current_price >= h1_ema200)
        macro_ok = vwap_aligned or ema_aligned
    else:
        vwap_aligned = (m15_vwap is not None and current_price <= m15_vwap)
        ema_aligned = (h1_ema200 is not None and current_price <= h1_ema200)
        macro_ok = vwap_aligned or ema_aligned

    # 5. ADR & News Guard
    adr_news_ok = (adr_used_pct < 80.0) and (not news_guard_active)

    points = {
        "sweep": bool(sweep_ok),
        "choch": bool(choch_ok),
        "fvg_retest": bool(fvg_ok),
        "macro_alignment": bool(macro_ok),
        "adr_news_clear": bool(adr_news_ok)
    }
    points_met = sum(1 for v in points.values() if v)

    # Calculate Execution Levels
    sl_distance = max(2.50, round(atr_m5 * 1.5, 2))
    reasons = []

    if direction == "BULLISH_LONG":
        entry_price = ce_level if (fvg_ok and ce_level) else current_price
        
        # Stop loss anchored below swing low or Asian Low
        if levels.asia_low is not None and levels.asia_low < entry_price:
            sl_price = round(min(levels.asia_low - 0.50, entry_price - sl_distance), 2)
        else:
            sl_price = round(entry_price - sl_distance, 2)
        
        actual_risk = round(entry_price - sl_price, 2)
        tp1_price = round(entry_price + (actual_risk * 2.0), 2)
        
        # Structural target (Asian High or PDH)
        tp2_price = round(levels.asia_high if levels.asia_high and levels.asia_high > entry_price else (entry_price + actual_risk * 3.5), 2)
        invalidation = f"M5 close below ${sl_price:.2f} invalidates bullish order block."

        if sweep_ok:
            reasons.append(f"Purged sell-side liquidity at Asian/PDL low (${levels.asia_low or levels.pdl:.2f}).")
        if choch_ok:
            reasons.append(f"Bullish M5 CHoCH confirmed above ${choch_level:.2f}.")
        if fvg_ok:
            reasons.append(f"Price retraced to unmitigated Bullish FVG 50% CE (${ce_level:.2f}).")
        if macro_ok:
            reasons.append("Macro alignment with Session VWAP / H1 200 EMA.")
        if adr_news_ok:
            reasons.append(f"ADR capacity healthy ({adr_used_pct:.0f}% used) with no imminent news.")

    else:  # BEARISH_SHORT
        entry_price = ce_level if (fvg_ok and ce_level) else current_price
        
        if levels.asia_high is not None and levels.asia_high > entry_price:
            sl_price = round(max(levels.asia_high + 0.50, entry_price + sl_distance), 2)
        else:
            sl_price = round(entry_price + sl_distance, 2)

        actual_risk = round(sl_price - entry_price, 2)
        tp1_price = round(entry_price - (actual_risk * 2.0), 2)
        tp2_price = round(levels.asia_low if levels.asia_low and levels.asia_low < entry_price else (entry_price - actual_risk * 3.5), 2)
        invalidation = f"M5 close above ${sl_price:.2f} invalidates bearish order block."

        if sweep_ok:
            reasons.append(f"Purged buy-side liquidity at Asian/PDH high (${levels.asia_high or levels.pdh:.2f}).")
        if choch_ok:
            reasons.append(f"Bearish M5 CHoCH confirmed below ${choch_level:.2f}.")
        if fvg_ok:
            reasons.append(f"Price retraced to unmitigated Bearish FVG 50% CE (${ce_level:.2f}).")
        if macro_ok:
            reasons.append("Macro alignment below Session VWAP / H1 200 EMA.")
        if adr_news_ok:
            reasons.append(f"ADR capacity healthy ({adr_used_pct:.0f}% used) with no imminent news.")

    # Grading & Confidence Score
    if points_met >= 4 and sweep_ok:
        grade = "GRADE_A"
        confidence = round(0.85 + (points_met - 4) * 0.08, 2)
        setup_type = f"{'Bullish' if direction == 'BULLISH_LONG' else 'Bearish'} Liquidity Sweep + M5 CHoCH Setup"
    elif points_met >= 3:
        grade = "GRADE_B"
        confidence = round(0.65 + (points_met - 3) * 0.10, 2)
        setup_type = f"{'Bullish' if direction == 'BULLISH_LONG' else 'Bearish'} Intraday Confluence Structure"
    else:
        grade = "NO_SETUP"
        confidence = round(points_met * 0.15, 2)
        setup_type = "Developing Setup / Insufficient Confluence"

    return SetupResult(
        grade=grade,
        direction=direction,
        confidence_score=min(confidence, 0.98),
        setup_type=setup_type,
        points_checked=points,
        points_met=points_met,
        suggested_entry=entry_price,
        suggested_sl=sl_price,
        suggested_tp1=tp1_price,
        suggested_tp2=tp2_price,
        risk_reward_ratio=2.0,
        invalidation_trigger=invalidation,
        reasons=reasons,
        timestamp=now_ts
    )
